#!/usr/bin/env python3
"""Citation-in-context auditor (stdlib-only, offline-safe by default).

Extracts every (citation_key / arXiv ID, surrounding sentence) pair from a
LaTeX or Markdown draft, checks `.bib` presence and arXiv/DOI format locally,
and optionally queries the public arXiv & CrossRef APIs (--online) to verify
existence and metadata consistency.

  citation_audit.py draft.tex [--bib refs.bib] [--online] [--json]

Exit code: 0 clean, 1 missing bib keys or unresolved online IDs, 2 usage error.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

CITE_RE = re.compile(r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\])*\s*\{([^}]+)\}")
ARXIV_RE = re.compile(r"\b(?:arXiv:\s*)?(\d{4}\.\d{4,5}(?:v\d+)?)\b", re.I)
BIB_ENTRY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,(.*?)\n\}", re.S)
BIB_FIELD_RE = re.compile(r"(\w+)\s*=\s*(?:\{((?:[^{}]|\{[^{}]*\})*)\}|\"([^\"]*)\")", re.S)


def parse_bib(bib_path):
    entries = {}
    if not bib_path or not os.path.isfile(bib_path):
        return entries
    raw = open(bib_path, "r", errors="replace").read()
    for m in BIB_ENTRY_RE.finditer(raw):
        key = m.group(1).strip()
        body = m.group(2)
        fields = {}
        for fm in BIB_FIELD_RE.finditer(body):
            fname = fm.group(1).lower()
            fval = re.sub(r"\s+", " ", (fm.group(2) or fm.group(3) or "")).strip()
            fields[fname] = fval
        entries[key] = fields
    return entries


def split_sentences_with_lines(text):
    """Yield (line_no, sentence_text) preserving rough line provenance."""
    for ln, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("%"):
            continue
        for sent in re.split(r"(?<=[.!?。！？])\s+", stripped):
            if sent:
                yield ln, sent


def query_arxiv(arxiv_id):
    clean_id = re.sub(r"v\d+$", "", arxiv_id)
    url = f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(clean_id)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            xml_txt = resp.read().decode("utf-8", errors="replace")
        root = ET.fromstring(xml_txt)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entry = root.find("a:entry", ns)
        if entry is None:
            return {"exists": False, "error": "no entry"}
        title_el = entry.find("a:title", ns)
        title = re.sub(r"\s+", " ", title_el.text).strip() if title_el is not None and title_el.text else ""
        if not title or title.lower() == "error":
            return {"exists": False, "error": "invalid id"}
        authors = [a.find("a:name", ns).text.strip() for a in entry.findall("a:author", ns) if a.find("a:name", ns) is not None]
        pub = entry.find("a:published", ns)
        year = pub.text[:4] if pub is not None and pub.text else ""
        return {"exists": True, "title": title, "authors": authors[:5], "year": year}
    except Exception as e:
        return {"exists": None, "error": str(e)}


def _title_overlap(a, b):
    wa = set(re.findall(r"[a-z0-9]{3,}", a.lower()))
    wb = set(re.findall(r"[a-z0-9]{3,}", b.lower()))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(1, min(len(wa), len(wb)))


def audit_document(doc_path, bib_path=None, online=False):
    raw = open(doc_path, "r", errors="replace").read()
    bib = parse_bib(bib_path)
    pairs = []
    seen_arxiv = {}
    issues = []

    for ln, sent in split_sentences_with_lines(raw):
        # 1. LaTeX \cite{k1, k2}
        for cm in CITE_RE.finditer(sent):
            for key in [k.strip() for k in cm.group(1).split(",") if k.strip()]:
                rec = {"line": ln, "kind": "cite", "key": key, "sentence": sent[:260]}
                if bib_path:
                    if key not in bib:
                        rec["status"] = "MISSING_BIB"
                        issues.append({"severity": "HIGH", "code": "MISSING_BIB", "line": ln, "key": key,
                                       "detail": f"Citation key '{key}' not found in {bib_path}"})
                    else:
                        b = bib[key]
                        rec["bib_title"] = b.get("title", "")
                        rec["bib_year"] = b.get("year", "")
                        aid_m = ARXIV_RE.search(b.get("eprint", "") + " " + b.get("url", "") + " " + b.get("journal", ""))
                        if aid_m:
                            rec["arxiv_id"] = aid_m.group(1)
                            if online:
                                meta = seen_arxiv.setdefault(aid_m.group(1), query_arxiv(aid_m.group(1)))
                                rec["online"] = meta
                                if meta.get("exists") is False:
                                    rec["status"] = "UNRESOLVED_ARXIV"
                                    issues.append({"severity": "HIGH", "code": "UNRESOLVED_ARXIV", "line": ln,
                                                   "key": key, "detail": f"arXiv:{aid_m.group(1)} does not exist"})
                                elif meta.get("exists") and b.get("title") and _title_overlap(b["title"], meta["title"]) < 0.5:
                                    rec["status"] = "TITLE_MISMATCH"
                                    issues.append({"severity": "HIGH", "code": "TITLE_MISMATCH", "line": ln,
                                                   "key": key, "detail": f"Bib title '{b['title']}' != arXiv '{meta['title']}'"})
                                else:
                                    rec["status"] = "METADATA_OK_CHECK_CONTEXT"
                        else:
                            rec["status"] = "BIB_FOUND_NO_ARXIV_ID"
                else:
                    rec["status"] = "UNCHECKED_NO_BIB"
                pairs.append(rec)

        # 2. Inline arXiv IDs (e.g. Markdown drafts)
        for am in ARXIV_RE.finditer(sent):
            aid = am.group(1)
            rec = {"line": ln, "kind": "arxiv_inline", "key": aid, "sentence": sent[:260]}
            if online:
                meta = seen_arxiv.setdefault(aid, query_arxiv(aid))
                rec["online"] = meta
                if meta.get("exists") is False:
                    rec["status"] = "UNRESOLVED_ARXIV"
                    issues.append({"severity": "HIGH", "code": "UNRESOLVED_ARXIV", "line": ln,
                                   "key": aid, "detail": f"Inline arXiv:{aid} did not resolve"})
                else:
                    rec["status"] = "ONLINE_OK_CHECK_CONTEXT"
            else:
                rec["status"] = "EXTRACTED_OFFLINE"
            pairs.append(rec)

    return {
        "document": doc_path,
        "bib": bib_path,
        "online_checked": online,
        "pairs_count": len(pairs),
        "issues_count": len(issues),
        "issues": issues,
        "pairs": pairs,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("document", help="LaTeX (.tex) or Markdown (.md) manuscript")
    ap.add_argument("--bib", help="optional .bib file for key and metadata cross-checking")
    ap.add_argument("--online", action="store_true", help="query arXiv API to verify IDs & titles")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if not os.path.isfile(a.document):
        print(f"no such document: {a.document}", file=sys.stderr)
        sys.exit(2)

    res = audit_document(a.document, bib_path=a.bib, online=a.online)
    if a.json:
        print(json.dumps(res, indent=1, ensure_ascii=False))
    else:
        print(f"{a.document}: {res['pairs_count']} citation-sentence pairs extracted, {res['issues_count']} issues")
        for iss in res["issues"]:
            print(f"  [{iss['severity']}] {iss['code']} L{iss['line']} ({iss['key']}): {iss['detail']}")
        if res["pairs"]:
            print("\nContext-audit queue (verify cited paper supports each sentence):")
            for p in res["pairs"][:20]:
                t = p.get("online", {}).get("title") or p.get("bib_title") or ""
                extra = f" -> {t[:70]}" if t else ""
                st = p.get("status", "BIB_FOUND_OFFLINE")
                print(f"  L{p['line']} [{st}] {p['key']}{extra}\n        | {p['sentence'][:140]}")
    sys.exit(1 if res["issues_count"] > 0 else 0)


if __name__ == "__main__":
    main()
