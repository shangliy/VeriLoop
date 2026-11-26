#!/usr/bin/env python3
"""Hard Citation & Literature Verification Gate (v2, stdlib-only, offline-safe by default).

Verifies LaTeX (.tex) or Markdown (.md) citations against local `.bib` files and,
when `--online` is passed, cross-checks every reference against three authoritative
academic APIs with zero third-party dependencies:
  1. arXiv API            (ID lookup + title search -> title, authors, year, abstract)
  2. Crossref API         (DOI lookup + bibliographic search -> title, authors, year, venue, retraction)
  3. Semantic Scholar API (ARXIV/DOI lookup + search -> title, authors, year, venue, abstract)

Capabilities:
  - Hard-gate detection of MISSING_BIB, UNRESOLVED_REFERENCE (fabricated papers),
    TITLE_MISMATCH, AUTHOR_MISMATCH, YEAR_MISMATCH (>1 yr lag), and RETRACTED_PAPER.
  - Deterministic claim-vs-abstract audit checking every citing sentence against the
    fetched real abstract (lexical grounding, polarity inversion, numeric mismatch),
    plus optional LLM semantic check (--claim-checker claude-cli|codex-cli).
  - Canonical BibTeX fetcher (--fetch-bib <id_or_doi_or_query> [--append-to refs.bib])
    so BibTeX entries come directly from authoritative APIs instead of LLM memory.

Usage:
  citation_audit.py draft.tex [--bib refs.bib] [--online] [--check-claims] [--json]
  citation_audit.py --fetch-bib 2605.03042 10.1145/... [--append-to paper/refs.bib]

Exit code: 0 clean, 1 hard gate failure (HIGH issues), 2 usage error.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

CITE_RE = re.compile(r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\])*\s*\{([^}]+)\}")
ARXIV_RE = re.compile(r"\b(?:arXiv:\s*)?(\d{4}\.\d{4,5}(?:v\d+)?)\b", re.I)
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b")
BIB_ENTRY_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,(.*?)\n\}", re.S)
BIB_FIELD_RE = re.compile(r"(\w+)\s*=\s*(?:\{((?:[^{}]|\{[^{}]*\})*)\}|\"([^\"]*)\"|(\d{4}))", re.S)
PCT_OR_DEC_RE = re.compile(r"(?<![\w.])(\d+\.\d+%?|\d{1,3}%)")

USER_AGENT = "VeriLoop-CitationGate/2.0 (https://github.com/shangliy/VeriLoop; mailto:veriloop@users.noreply.github.com)"

POS_CLAIM_RE = re.compile(
    r"\b(?:improv(?:e|es|ed|ing)|outperform(?:s|ed|ing)?|reduc(?:e|es|ed|ing)\s+(?:error|hallucination|leakage|failure|loss)|"
    r"eliminat(?:e|es|ed)|solv(?:e|es|ed)|succeed(?:s|ed)?|increase(?:s|d)?\s+(?:accuracy|recall|f1))\b",
    re.I,
)
NEG_CLAIM_RE = re.compile(
    r"\b(?:fail(?:s|ed|ing)?\s+to|does\s+not\s+(?:improve|outperform|prevent|stop|reduce)|"
    r"no\s+(?:significant\s+)?(?:improvement|gain|benefit|effect)|degrad(?:e|es|ed)|worse\s+than|cannot\s+(?:detect|prevent|verify))\b",
    re.I,
)
STOPWORDS = {
    "about", "above", "across", "after", "against", "their", "there", "these", "those", "which",
    "while", "where", "using", "based", "model", "models", "paper", "study", "method", "methods",
    "results", "results", "system", "systems", "approach", "through", "between", "within", "under",
    "without", "large", "language", "shows", "show", "report", "reports", "evaluated", "evaluates",
}


def parse_bib(bib_path):
    entries = {}
    if not bib_path or not os.path.isfile(bib_path):
        return entries
    with open(bib_path, "r", errors="replace") as fh:
        raw = fh.read()
    for m in BIB_ENTRY_RE.finditer(raw):
        etype = m.group(1).strip().lower()
        key = m.group(2).strip()
        body = m.group(3)
        fields = {"_type": etype}
        for fm in BIB_FIELD_RE.finditer(body):
            fname = fm.group(1).lower()
            raw_v = fm.group(2) if fm.group(2) is not None else (fm.group(3) if fm.group(3) is not None else (fm.group(4) or ""))
            fval = re.sub(r"\s+", " ", raw_v).strip()
            fields[fname] = fval
        entries[key] = fields
    return entries


def split_sentences_with_lines(text):
    """Yield (line_no, sentence_text) preserving line provenance."""
    for ln, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("%"):
            continue
        for sent in re.split(r"(?<=[.!?。！？])\s+", stripped):
            if sent:
                yield ln, sent


def _clean_latex(s):
    if not s:
        return ""
    s = re.sub(r"\\[a-zA-Z]+\*?\{([^}]*)\}", r"\1", s)
    s = re.sub(r"[{}]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _http_get_text(url, headers=None, timeout=15):
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _title_overlap(a, b):
    wa = set(re.findall(r"[a-z0-9]{3,}", _clean_latex(a).lower()))
    wb = set(re.findall(r"[a-z0-9]{3,}", _clean_latex(b).lower()))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(1, min(len(wa), len(wb)))


def _extract_surnames(author_field):
    """Extract normalized lowercase surnames from either BibTeX 'A and B' or list of strings."""
    if not author_field:
        return set()
    if isinstance(author_field, list):
        parts = [str(x) for x in author_field if x]
    else:
        parts = re.split(r"\s+and\s+", _clean_latex(str(author_field)), flags=re.I)
    surnames = set()
    for p in parts:
        p = p.strip()
        if not p or p.lower() in ("others", "et al.", "et al"):
            continue
        if "," in p:
            sn = p.split(",", 1)[0].strip()
        else:
            toks = [t for t in re.split(r"[\s.]+", p) if t]
            sn = toks[-1] if toks else ""
        sn = re.sub(r"[^a-z]", "", sn.lower())
        if len(sn) >= 2:
            surnames.add(sn)
    return surnames


def _extract_year(val):
    m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", str(val or ""))
    return int(m.group(1)) if m else None


def query_arxiv(arxiv_id):
    clean_id = re.sub(r"v\d+$", "", arxiv_id.strip())
    url = f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(clean_id)}"
    try:
        xml_txt = _http_get_text(url, timeout=15)
        root = ET.fromstring(xml_txt)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entry = root.find("a:entry", ns)
        if entry is None:
            return {"exists": False, "source": "arxiv", "error": "no entry"}
        title_el = entry.find("a:title", ns)
        title = re.sub(r"\s+", " ", title_el.text).strip() if title_el is not None and title_el.text else ""
        if not title or title.lower() == "error":
            return {"exists": False, "source": "arxiv", "error": "invalid id"}
        authors = [
            a.find("a:name", ns).text.strip()
            for a in entry.findall("a:author", ns)
            if a.find("a:name", ns) is not None and a.find("a:name", ns).text
        ]
        pub = entry.find("a:published", ns)
        year = pub.text[:4] if pub is not None and pub.text else ""
        summ = entry.find("a:summary", ns)
        abstract = re.sub(r"\s+", " ", summ.text).strip() if summ is not None and summ.text else ""
        return {
            "exists": True,
            "source": "arxiv",
            "arxiv_id": clean_id,
            "title": title,
            "authors": authors[:10],
            "year": year,
            "venue": f"arXiv preprint arXiv:{clean_id}",
            "abstract": abstract,
            "url": f"https://arxiv.org/abs/{clean_id}",
            "retracted": False,
        }
    except Exception as e:
        return {"exists": None, "source": "arxiv", "error": str(e)}


def query_crossref_doi(doi):
    clean_doi = doi.strip().rstrip(".,;)")
    url = f"https://api.crossref.org/works/{urllib.parse.quote(clean_doi, safe='')}"
    try:
        data = json.loads(_http_get_text(url, timeout=15))
        msg = data.get("message") or {}
        titles = msg.get("title") or []
        title = re.sub(r"\s+", " ", titles[0]).strip() if titles else ""
        if not title:
            return {"exists": False, "source": "crossref", "error": "empty title"}
        authors = []
        for a in msg.get("author") or []:
            nm = " ".join(x for x in (a.get("given", ""), a.get("family", "")) if x).strip()
            if nm:
                authors.append(nm)
        year = ""
        for field in ("published-print", "published-online", "issued", "created"):
            parts = ((msg.get(field) or {}).get("date-parts") or [[]])[0]
            if parts and parts[0]:
                year = str(parts[0])
                break
        venue = (msg.get("container-title") or [""])[0]
        abstract = re.sub(r"<[^>]+>", " ", msg.get("abstract") or "")
        abstract = re.sub(r"\s+", " ", abstract).strip()
        retracted = False
        for upd in msg.get("update-to") or []:
            if "retract" in str(upd.get("type", "")).lower() or "retract" in str(upd.get("label", "")).lower():
                retracted = True
        if "retracted" in title.lower():
            retracted = True
        return {
            "exists": True,
            "source": "crossref",
            "doi": clean_doi,
            "title": title,
            "authors": authors[:10],
            "year": year,
            "venue": venue,
            "abstract": abstract,
            "url": f"https://doi.org/{clean_doi}",
            "retracted": retracted,
        }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"exists": False, "source": "crossref", "error": "DOI 404 not found"}
        return {"exists": None, "source": "crossref", "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"exists": None, "source": "crossref", "error": str(e)}


def query_crossref_search(title, author=""):
    q = _clean_latex(f"{title} {author}".strip())
    if not q:
        return {"exists": False, "source": "crossref_search", "error": "empty query"}
    url = f"https://api.crossref.org/works?query.bibliographic={urllib.parse.quote(q)}&rows=3"
    try:
        data = json.loads(_http_get_text(url, timeout=15))
        items = (data.get("message") or {}).get("items") or []
        best = None
        best_score = 0.0
        for msg in items:
            t = re.sub(r"\s+", " ", (msg.get("title") or [""])[0]).strip()
            sc = _title_overlap(title, t) if title else 0.5
            if sc > best_score:
                best_score = sc
                best = msg
        if not best or (title and best_score < 0.5):
            return {"exists": False, "source": "crossref_search", "error": f"no matching title (best_overlap={best_score:.2f})"}
        doi = best.get("DOI", "")
        authors = [
            " ".join(x for x in (a.get("given", ""), a.get("family", "")) if x).strip()
            for a in (best.get("author") or [])
        ]
        year = ""
        for field in ("published-print", "published-online", "issued", "created"):
            parts = ((best.get(field) or {}).get("date-parts") or [[]])[0]
            if parts and parts[0]:
                year = str(parts[0])
                break
        venue = (best.get("container-title") or [""])[0]
        abstract = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", best.get("abstract") or "")).strip()
        retracted = any(
            "retract" in str(u.get("type", "")).lower() or "retract" in str(u.get("label", "")).lower()
            for u in (best.get("update-to") or [])
        )
        return {
            "exists": True,
            "source": "crossref_search",
            "doi": doi,
            "title": re.sub(r"\s+", " ", (best.get("title") or [""])[0]).strip(),
            "authors": [a for a in authors if a][:10],
            "year": year,
            "venue": venue,
            "abstract": abstract,
            "url": f"https://doi.org/{doi}" if doi else best.get("URL", ""),
            "retracted": retracted,
        }
    except Exception as e:
        return {"exists": None, "source": "crossref_search", "error": str(e)}


def query_semantic_scholar(paper_id=None, title=None):
    fields = "title,authors,year,venue,abstract,externalIds,url"
    headers = {}
    if os.environ.get("S2_API_KEY"):
        headers["x-api-key"] = os.environ["S2_API_KEY"]
    try:
        if paper_id:
            url = f"https://api.semanticscholar.org/graph/v1/paper/{urllib.parse.quote(paper_id, safe=':/')}?fields={fields}"
            d = json.loads(_http_get_text(url, headers=headers, timeout=15))
        elif title:
            q = _clean_latex(title)
            url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={urllib.parse.quote(q)}&limit=3&fields={fields}"
            res = json.loads(_http_get_text(url, headers=headers, timeout=15))
            items = res.get("data") or []
            best = None
            best_sc = 0.0
            for it in items:
                sc = _title_overlap(q, it.get("title") or "")
                if sc > best_sc:
                    best_sc = sc
                    best = it
            if not best or best_sc < 0.5:
                return {"exists": False, "source": "semantic_scholar", "error": f"no S2 match (best={best_sc:.2f})"}
            d = best
        else:
            return {"exists": False, "source": "semantic_scholar", "error": "no id or title"}

        if not d.get("title"):
            return {"exists": False, "source": "semantic_scholar", "error": "empty S2 response"}
        ext = d.get("externalIds") or {}
        return {
            "exists": True,
            "source": "semantic_scholar",
            "title": re.sub(r"\s+", " ", d["title"]).strip(),
            "authors": [a.get("name", "").strip() for a in (d.get("authors") or []) if a.get("name")][:10],
            "year": str(d.get("year") or ""),
            "venue": str(d.get("venue") or ""),
            "arxiv_id": ext.get("ArXiv", ""),
            "doi": ext.get("DOI", ""),
            "abstract": re.sub(r"\s+", " ", d.get("abstract") or "").strip(),
            "url": d.get("url") or "",
            "retracted": False,
        }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"exists": False, "source": "semantic_scholar", "error": "S2 404"}
        return {"exists": None, "source": "semantic_scholar", "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"exists": None, "source": "semantic_scholar", "error": str(e)}


def resolve_reference_online(bib_entry, cache=None):
    """Multi-provider authoritative resolution: arXiv -> Crossref -> Semantic Scholar."""
    cache = cache if cache is not None else {}
    raw_id_blob = " ".join(bib_entry.get(k, "") for k in ("eprint", "doi", "url", "journal", "booktitle", "note"))
    title = _clean_latex(bib_entry.get("title", ""))
    author = _clean_latex(bib_entry.get("author", ""))

    aid_m = ARXIV_RE.search(raw_id_blob)
    doi_m = DOI_RE.search(bib_entry.get("doi", "") + " " + bib_entry.get("url", ""))

    ckey = (aid_m.group(1) if aid_m else "", doi_m.group(1) if doi_m else "", title.lower())
    if ckey in cache:
        return cache[ckey]

    meta = None
    # 1. Exact arXiv ID lookup (most reliable for CS/ML preprints; includes abstract)
    if aid_m:
        aid = aid_m.group(1)
        meta = query_arxiv(aid)
        if meta.get("exists") is not True:
            # Try S2 fallback for arXiv ID
            s2 = query_semantic_scholar(paper_id=f"ARXIV:{re.sub(r'v\\d+$', '', aid)}")
            if s2.get("exists") is True:
                meta = s2
    # 2. Exact DOI lookup via Crossref (authoritative + retraction notices)
    if (meta is None or meta.get("exists") is not True) and doi_m:
        cr = query_crossref_doi(doi_m.group(1))
        if cr.get("exists") is True:
            meta = cr
            # Enrich missing abstract from S2 when Crossref omits it
            if not meta.get("abstract"):
                s2 = query_semantic_scholar(paper_id=f"DOI:{doi_m.group(1)}")
                if s2.get("exists") is True and s2.get("abstract"):
                    meta["abstract"] = s2["abstract"]
        elif meta is None:
            meta = cr
    # 3. Title/author lookup via Semantic Scholar -> Crossref search -> arXiv title search
    if (meta is None or meta.get("exists") is None) and title:
        s2 = query_semantic_scholar(title=title)
        if s2.get("exists") is True:
            meta = s2
        else:
            cr_s = query_crossref_search(title, author)
            if cr_s.get("exists") is True:
                meta = cr_s
                if not meta.get("abstract") and cr_s.get("doi"):
                    s2_abs = query_semantic_scholar(paper_id=f"DOI:{cr_s['doi']}")
                    if s2_abs.get("exists") is True and s2_abs.get("abstract"):
                        meta["abstract"] = s2_abs["abstract"]
            elif meta is None:
                meta = cr_s if cr_s.get("exists") is False else s2

    if meta is None:
        meta = {"exists": False, "source": "none", "error": "no arxiv/doi/title to resolve"}
    cache[ckey] = meta
    return meta


def check_claim_vs_abstract(sentence, meta):
    """Deterministic claim-vs-abstract consistency check ($0).

    Checks:
      - Whether numeric figures cited in the sentence appear in the fetched abstract.
      - Whether polarity (positive gain vs explicit negation/failure) contradicts the abstract.
      - Content-word lexical grounding between citing sentence and title+abstract.
    """
    abstract = (meta or {}).get("abstract") or ""
    title = (meta or {}).get("title") or ""
    if not abstract:
        return {"status": "NO_ABSTRACT_AVAILABLE", "overlap": 0.0, "ungrounded_numbers": [], "polarity_conflict": False}

    ref_text = f"{title} {abstract}".lower()
    sent_clean = _clean_latex(sentence).lower()

    sent_words = {w for w in re.findall(r"[a-z]{4,}", sent_clean) if w not in STOPWORDS}
    ref_words = {w for w in re.findall(r"[a-z]{4,}", ref_text) if w not in STOPWORDS}
    overlap = len(sent_words & ref_words) / max(1, min(len(sent_words), 12))

    # Check numbers quoted in the citing sentence against the abstract
    abs_nums = set(re.findall(r"\d+\.\d+|\d{1,3}%", ref_text))
    sent_nums = [m.group(1) for m in PCT_OR_DEC_RE.finditer(sent_clean)]
    ungrounded_nums = []
    for sn in sent_nums:
        bare = sn.rstrip("%")
        if sn not in abs_nums and bare not in abs_nums:
            ungrounded_nums.append(sn)

    # Check explicit polarity inversion (e.g. citing paper says X improves/eliminates while abstract says X fails/does not)
    s_pos = bool(POS_CLAIM_RE.search(sent_clean)) and not bool(NEG_CLAIM_RE.search(sent_clean))
    s_neg = bool(NEG_CLAIM_RE.search(sent_clean))
    a_pos = bool(POS_CLAIM_RE.search(abstract.lower())) and not bool(NEG_CLAIM_RE.search(abstract.lower()))
    a_neg = bool(NEG_CLAIM_RE.search(abstract.lower()))
    polarity_conflict = (s_pos and a_neg and not a_pos) or (s_neg and a_pos and not a_neg)

    if polarity_conflict:
        status = "POTENTIAL_CONTRADICTION"
    elif ungrounded_nums:
        status = "NUMBERS_NOT_IN_ABSTRACT_VERIFY_BODY"
    elif overlap < 0.15 and len(sent_words) >= 5:
        status = "LOW_LEXICAL_GROUNDING"
    else:
        status = "GROUNDED_IN_ABSTRACT"

    return {
        "status": status,
        "overlap": round(overlap, 3),
        "ungrounded_numbers": ungrounded_nums,
        "polarity_conflict": polarity_conflict,
    }


def check_claim_with_llm(sentence, meta, provider):
    """Optional read-only LLM semantic contradiction check against real fetched abstract."""
    abstract = (meta or {}).get("abstract") or ""
    if not abstract or provider == "none":
        return None
    prompt = (
        "You are a strict scientific citation auditor. Compare the manuscript sentence against the "
        "cited paper's REAL title and abstract. Reply with a single JSON object: "
        '{"verdict": "SUPPORTED"|"NOT_IN_ABSTRACT"|"CONTRADICTED", "reason": "<one crisp sentence>"}.\n\n'
        f"Cited Title: {meta.get('title', '')}\n"
        f"Cited Year: {meta.get('year', '')}\n"
        f"Real Abstract: {abstract[:2200]}\n\n"
        f"Manuscript Sentence: {sentence}\n"
    )
    try:
        if provider == "claude-cli":
            p = subprocess.run(
                ["claude", "-p", "--output-format", "text", "--model", "haiku", "--no-session-persistence"],
                input=prompt, capture_output=True, text=True, timeout=60,
            )
            raw = p.stdout
        elif provider == "codex-cli":
            p = subprocess.run(["codex", "exec", "-"], input=prompt, capture_output=True, text=True, timeout=60)
            raw = p.stdout
        else:
            return None
        m = re.search(r"\{[^{}]*\"verdict\"[^{}]*\}", raw, re.S)
        if m:
            return json.loads(m.group(0))
    except Exception as e:
        return {"verdict": "ERROR", "reason": str(e)[:120]}
    return None


def format_bibtex(meta, key=None):
    """Generate a clean canonical BibTeX entry directly from verified API metadata."""
    authors = meta.get("authors") or ["Unknown"]
    year = meta.get("year") or "2026"
    title = meta.get("title") or "Untitled"
    first_surname = next(iter(_extract_surnames([authors[0]])), "paper")
    first_word = next(iter(re.findall(r"[a-z]{4,}", title.lower())), "work")
    bib_key = key or f"{first_surname}{year}{first_word}"
    author_str = " and ".join(authors)
    is_arxiv_only = bool(meta.get("arxiv_id")) and (not meta.get("venue") or "arxiv" in meta.get("venue", "").lower())
    etype = "article"
    lines = [
        f"@{etype}{{{bib_key},",
        f"  title={{{{{title}}}}},",
        f"  author={{{author_str}}},",
        f"  year={{{year}}},",
    ]
    if is_arxiv_only:
        lines.append(f"  journal={{arXiv preprint arXiv:{meta['arxiv_id']}}},")
        lines.append(f"  eprint={{{meta['arxiv_id']}}},")
        lines.append("  archivePrefix={arXiv},")
    elif meta.get("venue"):
        lines.append(f"  journal={{{meta['venue']}}},")
    if meta.get("doi"):
        lines.append(f"  doi={{{meta['doi']}}},")
    if meta.get("url"):
        lines.append(f"  url={{{meta['url']}}},")
    lines.append("}")
    return "\n".join(lines)


def fetch_bibtex_entries(queries):
    """Resolve arXiv IDs, DOIs, or titles and return (entries_list, errors_list)."""
    entries, errors = [], []
    for q in queries:
        q = q.strip()
        if ARXIV_RE.fullmatch(q):
            m = ARXIV_RE.fullmatch(q)
            meta = resolve_reference_online({"eprint": m.group(1)})
        elif DOI_RE.fullmatch(q):
            meta = resolve_reference_online({"doi": q})
        else:
            meta = resolve_reference_online({"title": q})
        if meta.get("exists") is True:
            entries.append({"query": q, "meta": meta, "bibtex": format_bibtex(meta)})
        else:
            errors.append({"query": q, "error": meta.get("error", "unresolved")})
    return entries, errors


def audit_document(doc_path, bib_path=None, online=False, check_claims=False, claim_checker="none"):
    with open(doc_path, "r", errors="replace") as fh:
        raw = fh.read()
    bib = parse_bib(bib_path)
    pairs = []
    cache = {}
    issues = []
    warnings = []

    for ln, sent in split_sentences_with_lines(raw):
        # 1. LaTeX \cite{k1, k2}
        for cm in CITE_RE.finditer(sent):
            for key in [k.strip() for k in cm.group(1).split(",") if k.strip()]:
                rec = {"line": ln, "kind": "cite", "key": key, "sentence": sent[:300]}
                if bib_path:
                    if key not in bib:
                        rec["status"] = "MISSING_BIB"
                        issues.append({
                            "severity": "HIGH", "code": "MISSING_BIB", "line": ln, "key": key,
                            "detail": f"Citation key '{key}' not found in {bib_path}",
                        })
                    else:
                        b = bib[key]
                        rec["bib_title"] = b.get("title", "")
                        rec["bib_author"] = b.get("author", "")
                        rec["bib_year"] = b.get("year", "")
                        aid_m = ARXIV_RE.search(b.get("eprint", "") + " " + b.get("url", "") + " " + b.get("journal", ""))
                        doi_m = DOI_RE.search(b.get("doi", "") + " " + b.get("url", ""))
                        if aid_m:
                            rec["arxiv_id"] = aid_m.group(1)
                        if doi_m:
                            rec["doi"] = doi_m.group(1)

                        if online:
                            meta = resolve_reference_online(b, cache=cache)
                            rec["online"] = meta
                            if meta.get("exists") is False:
                                rec["status"] = "UNRESOLVED_REFERENCE"
                                issues.append({
                                    "severity": "HIGH", "code": "UNRESOLVED_REFERENCE", "line": ln, "key": key,
                                    "detail": f"Reference '{key}' could not be verified on arXiv/Crossref/S2 ({meta.get('error', '')})",
                                })
                            elif meta.get("exists") is True:
                                key_issues = []
                                if meta.get("retracted"):
                                    key_issues.append(("RETRACTED_PAPER", f"Cited work '{key}' carries a Crossref retraction notice!"))
                                if b.get("title") and meta.get("title") and _title_overlap(b["title"], meta["title"]) < 0.55:
                                    key_issues.append((
                                        "TITLE_MISMATCH",
                                        f"Bib title '{_clean_latex(b['title'])}' != API '{meta['title']}' ({meta.get('source')})",
                                    ))
                                bib_surnames = _extract_surnames(b.get("author", ""))
                                api_surnames = _extract_surnames(meta.get("authors") or [])
                                if bib_surnames and api_surnames and not (bib_surnames & api_surnames):
                                    key_issues.append((
                                        "AUTHOR_MISMATCH",
                                        f"Bib authors {sorted(bib_surnames)[:3]} share no surname with API {sorted(api_surnames)[:3]}",
                                    ))
                                by, ay = _extract_year(b.get("year")), _extract_year(meta.get("year"))
                                if by and ay and abs(by - ay) > 1:
                                    key_issues.append((
                                        "YEAR_MISMATCH",
                                        f"Bib year {by} differs from API year {ay} by >1 year ({meta.get('source')})",
                                    ))
                                if key_issues:
                                    rec["status"] = key_issues[0][0]
                                    for code, det in key_issues:
                                        issues.append({"severity": "HIGH", "code": code, "line": ln, "key": key, "detail": det})
                                else:
                                    rec["status"] = "VERIFIED_ONLINE"

                                if check_claims:
                                    cva = check_claim_vs_abstract(sent, meta)
                                    rec["claim_vs_abstract"] = cva
                                    if cva["status"] == "POTENTIAL_CONTRADICTION":
                                        warnings.append({
                                            "severity": "MEDIUM", "code": "CLAIM_ABSTRACT_POLARITY_CONFLICT",
                                            "line": ln, "key": key,
                                            "detail": f"Polarity mismatch between citing sentence and fetched abstract for '{key}'",
                                        })
                                    if claim_checker != "none":
                                        llm_chk = check_claim_with_llm(sent, meta, claim_checker)
                                        rec["llm_claim_check"] = llm_chk
                                        if llm_chk and llm_chk.get("verdict") == "CONTRADICTED":
                                            issues.append({
                                                "severity": "HIGH", "code": "CLAIM_CONTRADICTS_ABSTRACT",
                                                "line": ln, "key": key,
                                                "detail": f"LLM abstract audit flagged contradiction: {llm_chk.get('reason', '')}",
                                            })
                            else:
                                rec["status"] = "API_UNREACHABLE"
                                warnings.append({
                                    "severity": "MEDIUM", "code": "API_UNREACHABLE", "line": ln, "key": key,
                                    "detail": f"Online API lookup inconclusive ({meta.get('error', '')})",
                                })
                        else:
                            rec["status"] = "BIB_FOUND_OFFLINE" if (aid_m or doi_m) else "BIB_FOUND_NO_ARXIV_ID"
                else:
                    rec["status"] = "UNCHECKED_NO_BIB"
                pairs.append(rec)

        # 2. Inline arXiv IDs (e.g. Markdown drafts)
        for am in ARXIV_RE.finditer(sent):
            aid = am.group(1)
            rec = {"line": ln, "kind": "arxiv_inline", "key": aid, "sentence": sent[:300]}
            if online:
                meta = resolve_reference_online({"eprint": aid}, cache=cache)
                rec["online"] = meta
                if meta.get("exists") is False:
                    rec["status"] = "UNRESOLVED_ARXIV"
                    issues.append({
                        "severity": "HIGH", "code": "UNRESOLVED_ARXIV", "line": ln, "key": aid,
                        "detail": f"Inline arXiv:{aid} did not resolve",
                    })
                elif meta.get("exists") is True:
                    rec["status"] = "ONLINE_OK_CHECK_CONTEXT"
                    if check_claims:
                        rec["claim_vs_abstract"] = check_claim_vs_abstract(sent, meta)
                else:
                    rec["status"] = "API_UNREACHABLE"
            else:
                rec["status"] = "EXTRACTED_OFFLINE"
            pairs.append(rec)

    return {
        "document": doc_path,
        "bib": bib_path,
        "online_checked": online,
        "claims_checked": check_claims,
        "pairs_count": len(pairs),
        "issues_count": len(issues),
        "warnings_count": len(warnings),
        "issues": issues,
        "warnings": warnings,
        "pairs": pairs,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("document", nargs="?", help="LaTeX (.tex) or Markdown (.md) manuscript")
    ap.add_argument("--bib", help="Optional .bib file for key and metadata cross-checking")
    ap.add_argument("--online", action="store_true", help="Query arXiv / Crossref / Semantic Scholar APIs to verify existence, title, authors, year, and retractions")
    ap.add_argument("--check-claims", action="store_true", help="Check citing sentences against fetched real abstracts (requires --online)")
    ap.add_argument("--claim-checker", choices=("none", "claude-cli", "codex-cli"), default="none",
                    help="Optional LLM semantic contradiction judge on fetched abstracts")
    ap.add_argument("--fetch-bib", nargs="+", default=[], help="Fetch canonical BibTeX entries from arXiv/Crossref/S2 by ID, DOI, or title")
    ap.add_argument("--append-to", help="Append fetched BibTeX entries to this .bib file")
    ap.add_argument("--strict-warnings", action="store_true", help="Exit 1 on MEDIUM warnings (e.g. claim polarity conflict or unreachable API)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.fetch_bib:
        entries, errors = fetch_bibtex_entries(a.fetch_bib)
        if a.append_to and entries:
            with open(a.append_to, "a", encoding="utf-8") as fh:
                for e in entries:
                    fh.write("\n" + e["bibtex"] + "\n")
        if a.json:
            print(json.dumps({"fetched": entries, "errors": errors}, indent=2, ensure_ascii=False))
        else:
            for e in entries:
                print(e["bibtex"] + "\n")
            for err in errors:
                print(f"[UNRESOLVED] {err['query']}: {err['error']}", file=sys.stderr)
        sys.exit(1 if errors else 0)

    if not a.document or not os.path.isfile(a.document):
        print(f"no such document: {a.document}", file=sys.stderr)
        sys.exit(2)

    res = audit_document(
        a.document,
        bib_path=a.bib,
        online=a.online,
        check_claims=a.check_claims,
        claim_checker=a.claim_checker,
    )
    if a.json:
        print(json.dumps(res, indent=1, ensure_ascii=False))
    else:
        print(
            f"{a.document}: {res['pairs_count']} citation-sentence pairs extracted, "
            f"{res['issues_count']} issues, {res['warnings_count']} warnings"
        )
        for iss in res["issues"]:
            print(f"  [{iss['severity']}] {iss['code']} L{iss['line']} ({iss['key']}): {iss['detail']}")
        for w in res["warnings"]:
            print(f"  [{w['severity']}] {w['code']} L{w['line']} ({w['key']}): {w['detail']}")
        if res["pairs"]:
            print("\nContext-audit queue (verify cited paper supports each sentence):")
            for p in res["pairs"][:25]:
                t = p.get("online", {}).get("title") or p.get("bib_title") or ""
                extra = f" -> {t[:70]}" if t else ""
                st = p.get("status", "BIB_FOUND_OFFLINE")
                cva = p.get("claim_vs_abstract")
                cva_s = f" | abstract={cva['status']}" if cva else ""
                print(f"  L{p['line']} [{st}{cva_s}] {p['key']}{extra}\n        | {p['sentence'][:140]}")
    failed = res["issues_count"] > 0 or (a.strict_warnings and res["warnings_count"] > 0)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
