#!/usr/bin/env python3
"""VeriLoop Paper & Codebase Ingestion Engine (`./veriloop ingest`).

Downloads arXiv LaTeX e-print source archives (or reads local .tex/.tar.gz files),
extracts sections, equations, hyperparameters, and referenced GitHub repositories,
indexes a target baseline Python repository via static AST (no code execution),
and builds a structured Formula/Concept <-> Code (`file:line`) alignment map plus
a Layer-2 verification watchlist for `wiki/INGEST_MAP.md`.

Zero external Python dependencies (stdlib only).
"""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT = "VeriLoop-Ingest/5.0 (https://github.com/shangliy/VeriLoop)"
ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+/\d{7}(?:v\d+)?)")
GITHUB_URL_RE = re.compile(r"https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")

STOPWORDS = frozenset({
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were",
    "into", "over", "under", "using", "used", "use", "our", "we", "can", "may",
    "also", "such", "than", "then", "when", "where", "which", "while", "each",
    "both", "all", "any", "not", "but", "its", "their", "have", "has", "been",
    "self", "none", "true", "false", "return", "def", "class", "init", "args",
    "kwargs", "data", "model", "input", "output", "value", "values", "result",
    "begin", "end", "frac", "left", "right", "text", "mathrm", "mathbf", "mathcal",
    "equation", "align", "label", "ref", "cite", "citep", "citet", "sum", "prod",
})

KEY_TORCH_OPS = (
    "softmax", "log_softmax", "cross_entropy", "kl_div", "mse_loss", "nll_loss",
    "einsum", "matmul", "bmm", "conv2d", "batch_norm", "layer_norm", "dropout",
    "attention", "scaled_dot_product", "sigmoid", "relu", "gelu", "silu",
    "backward", "grad", "clamp", "exp", "log", "norm", "cosine", "mixup",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_arxiv_id(raw: str) -> str:
    m = ARXIV_ID_RE.search(raw.strip())
    return m.group(1) if m else raw.strip()


def tokenize_identifier(text: str) -> set[str]:
    """Split camelCase, snake_case, LaTeX commands, and prose into normalized tokens."""
    # Expand camelCase
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    # Strip common LaTeX control words while keeping inner identifiers
    s = re.sub(r"\\(mathrm|mathbf|mathcal|text|operatorname|boldsymbol|hat|tilde|bar|vec)\{([^}]*)\}", r" \2 ", s)
    s = re.sub(r"\\[a-zA-Z]+", " ", s)
    toks = re.findall(r"[a-zA-Z][a-zA-Z0-9]{1,}", s.lower())
    return {t for t in toks if len(t) >= 2 and t not in STOPWORDS}


def fetch_arxiv_metadata(arxiv_id: str, timeout: int = 20) -> dict:
    clean_id = re.sub(r"v\d+$", "", normalize_arxiv_id(arxiv_id))
    url = f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(clean_id)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entry = root.find("a:entry", ns)
        if entry is None:
            return {"arxiv_id": clean_id}
        title = re.sub(r"\s+", " ", (entry.findtext("a:title", "", ns) or "").strip())
        summary = re.sub(r"\s+", " ", (entry.findtext("a:summary", "", ns) or "").strip())
        published = (entry.findtext("a:published", "", ns) or "")[:4]
        authors = [a.findtext("a:name", "", ns).strip() for a in entry.findall("a:author", ns)]
        return {
            "arxiv_id": clean_id,
            "title": title,
            "authors": [a for a in authors if a],
            "year": published,
            "abstract": summary,
            "url": f"https://arxiv.org/abs/{clean_id}",
        }
    except Exception as exc:
        return {"arxiv_id": clean_id, "metadata_error": str(exc)}


def _safe_extract_tar_tex(raw_bytes: bytes, dest_dir: Path) -> list[Path]:
    """Safely extract .tex/.bib files from tar/tar.gz/gz/plain-tex payloads (anti path-traversal)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    # 1. Try tar / tar.gz
    try:
        with tarfile.open(fileobj=io.BytesIO(raw_bytes), mode="r:*") as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                name = member.name.lstrip("/").replace("\\", "/")
                parts = [p for p in Path(name).parts if p not in ("", ".", "..")]
                if not parts:
                    continue
                if not name.lower().endswith((".tex", ".bib", ".sty")):
                    continue
                out_p = (dest_dir / Path(*parts)).resolve()
                if not str(out_p).startswith(str(dest_dir.resolve())):
                    continue
                out_p.parent.mkdir(parents=True, exist_ok=True)
                fh = tf.extractfile(member)
                if fh is not None:
                    out_p.write_bytes(fh.read())
                    extracted.append(out_p)
            if extracted:
                return extracted
    except tarfile.TarError:
        pass

    # 2. Try single gzipped .tex
    try:
        unpacked = gzip.decompress(raw_bytes)
        if b"\\documentclass" in unpacked or b"\\section" in unpacked or b"\\begin{" in unpacked:
            out_p = dest_dir / "main.tex"
            out_p.write_bytes(unpacked)
            return [out_p]
    except OSError:
        pass

    # 3. Plain text .tex
    if b"\\section" in raw_bytes or b"\\begin{" in raw_bytes or b"\\documentclass" in raw_bytes:
        out_p = dest_dir / "main.tex"
        out_p.write_bytes(raw_bytes)
        return [out_p]
    return []


def download_arxiv_source(arxiv_id: str, dest_dir: Path, timeout: int = 30) -> tuple[list[Path], str | None]:
    clean_id = normalize_arxiv_id(arxiv_id)
    url = f"https://arxiv.org/e-print/{urllib.parse.quote(clean_id)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        files = _safe_extract_tar_tex(raw, dest_dir)
        return files, (None if files else "no .tex files found in e-print archive (PDF-only submission?)")
    except Exception as exc:
        return [], str(exc)


def parse_latex_corpus(tex_files: list[Path], source_label: str) -> dict:
    """Extract title, sections, math equations, key hyperparams, and GitHub URLs from LaTeX sources."""
    combined_parts = []
    for p in sorted(tex_files):
        if p.suffix.lower() != ".tex":
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        # Strip LaTeX comments (preserving escaped \%)
        cleaned = re.sub(r"(?<!\\)%.*$", "", txt, flags=re.MULTILINE)
        combined_parts.append((p.name, cleaned))

    full_text = "\n\n".join(c for _, c in combined_parts)

    # Title & Abstract
    m_title = re.search(r"\\(?:icml)?title(?:\[[^\]]*\])?\{(.*?)\}", full_text, re.DOTALL)
    title = re.sub(r"\s+", " ", m_title.group(1)).strip() if m_title else source_label
    m_abs = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", full_text, re.DOTALL)
    abstract = re.sub(r"\s+", " ", m_abs.group(1)).strip() if m_abs else ""

    # Sections
    sections = []
    for m in re.finditer(r"\\(section|subsection)\*?\{([^}]{2,120})\}", full_text):
        sections.append({"level": m.group(1), "heading": re.sub(r"\s+", " ", m.group(2)).strip()})

    # Display equations (equation, align, gather, \[...\]) with nearby context
    equations = []
    eq_patterns = [
        re.compile(r"\\begin\{(equation\*?|align\*?|gather\*?|multline\*?)\}(.*?)\\end\{\1\}", re.DOTALL),
        re.compile(r"\\\[(.*?)\\\]", re.DOTALL),
    ]
    seen_eqs = set()
    for fname, content in combined_parts:
        for pat in eq_patterns:
            for m in pat.finditer(content):
                body = m.group(2) if m.lastindex and m.lastindex >= 2 else m.group(1)
                body_clean = re.sub(r"\s+", " ", body).strip()
                if len(body_clean) < 8 or body_clean in seen_eqs:
                    continue
                seen_eqs.add(body_clean)
                line_no = content[: m.start()].count("\n") + 1
                raw_before = content[max(0, m.start() - 260) : m.start()]
                for sep in (
                    r"\end{equation}", r"\end{equation*}", r"\end{align}", r"\end{align*}",
                    r"\end{gather}", r"\end{gather*}", r"\end{multline}", r"\end{multline*}",
                    r"\]", "\n\n",
                ):
                    idx = raw_before.rfind(sep)
                    if idx != -1:
                        raw_before = raw_before[idx + len(sep) :]
                raw_after = content[m.end() : min(len(content), m.end() + 180)]
                for sep in (r"\begin{equation", r"\begin{align", r"\begin{gather", r"\begin{multline", r"\[", "\n\n"):
                    idx = raw_after.find(sep)
                    if idx != -1:
                        raw_after = raw_after[:idx]
                ctx_before = re.sub(r"\s+", " ", raw_before).strip()
                ctx_after = re.sub(r"\s+", " ", raw_after).strip()
                m_lbl = re.search(r"\\label\{([^}]+)\}", body)
                eq_label = m_lbl.group(1) if m_lbl else f"eq_{len(equations)+1}"
                tokens = sorted(tokenize_identifier(f"{eq_label} {ctx_before} {body_clean} {ctx_after}"))
                equations.append({
                    "id": eq_label,
                    "file": fname,
                    "line": line_no,
                    "latex": body_clean[:320],
                    "context": ctx_before[-180:],
                    "tokens": tokens[:40],
                })

    # GitHub URLs mentioned in paper
    gh_urls = sorted({
        re.sub(r"[.,;)\]}\\]+$", "", u)
        for u in GITHUB_URL_RE.findall(full_text)
    })

    # Common hyperparameter / dataset mentions
    hp_hits = []
    for pat, label in [
        (r"(?:learning rate|lr)\s*(?:of|=|:)?\s*((?=[0-9eE.\-×\\^]*\d)[0-9eE.\-×\\^]+)", "learning_rate"),
        (r"batch size\s*(?:of|=|:)?\s*(\d+)", "batch_size"),
        (r"weight decay\s*(?:of|=|:)?\s*((?=[0-9eE.\-×\\^]*\d)[0-9eE.\-×\\^]+)", "weight_decay"),
        (r"(\d+)\s+epochs?", "epochs"),
        (r"dropout\s*(?:rate|of|=|:)?\s*(0?\.\d+)", "dropout"),
    ]:
        found = sorted(set(re.findall(pat, full_text, re.IGNORECASE)))[:5]
        if found:
            hp_hits.append({"param": label, "values": found})

    return {
        "source": source_label,
        "title": title,
        "abstract": abstract[:1200],
        "tex_files": [p.name for p in sorted(tex_files) if p.suffix.lower() == ".tex"],
        "sections": sections[:40],
        "equations": equations[:35],
        "github_urls": gh_urls,
        "hyperparams": hp_hits,
    }


def index_python_codebase(repo_dir: Path, max_files: int = 250) -> list[dict]:
    """Statically index classes & functions via Python AST (zero code execution)."""
    symbols: list[dict] = []
    py_files = [
        p for p in sorted(repo_dir.rglob("*.py"))
        if ".git" not in p.parts and "__pycache__" not in p.parts and "site-packages" not in p.parts
    ][:max_files]

    for fp in py_files:
        rel = str(fp.relative_to(repo_dir))
        try:
            src = fp.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(src, filename=rel)
        except (OSError, SyntaxError):
            continue

        lines = src.splitlines()

        def _extract_ops(node: ast.AST) -> list[str]:
            found = set()
            for sub in ast.walk(node):
                if isinstance(sub, ast.Attribute) and sub.attr.lower() in KEY_TORCH_OPS:
                    found.add(sub.attr.lower())
                elif isinstance(sub, ast.Name) and sub.id.lower() in KEY_TORCH_OPS:
                    found.add(sub.id.lower())
            return sorted(found)

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                bases = [ast.unparse(b) for b in node.bases] if hasattr(ast, "unparse") else []
                doc = (ast.get_docstring(node) or "").splitlines()[0][:140] if ast.get_docstring(node) else ""
                methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                snippet = "\n".join(lines[node.lineno - 1 : min(len(lines), getattr(node, "end_lineno", node.lineno + 20))])
                toks = sorted(tokenize_identifier(f"{node.name} {' '.join(bases)} {doc} {' '.join(methods)} {snippet[:1200]}"))
                symbols.append({
                    "kind": "nn_module" if any("Module" in b for b in bases) else "class",
                    "name": node.name,
                    "file": rel,
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "bases": bases,
                    "methods": methods[:12],
                    "doc": doc,
                    "ops": _extract_ops(node),
                    "tokens": toks[:50],
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = (ast.get_docstring(node) or "").splitlines()[0][:140] if ast.get_docstring(node) else ""
                args = [a.arg for a in node.args.args]
                snippet = "\n".join(lines[node.lineno - 1 : min(len(lines), getattr(node, "end_lineno", node.lineno + 20))])
                toks = sorted(tokenize_identifier(f"{node.name} {' '.join(args)} {doc} {snippet[:1200]}"))
                symbols.append({
                    "kind": "function",
                    "name": node.name,
                    "file": rel,
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "args": args[:10],
                    "doc": doc,
                    "ops": _extract_ops(node),
                    "tokens": toks[:50],
                })
    return symbols


def align_formulas_to_code(papers: list[dict], symbols: list[dict], min_overlap: int = 2) -> tuple[list[dict], list[dict]]:
    """Match paper equations & method sections to AST code symbols; flag unmatched formulas."""
    alignments = []
    unmatched = []
    sym_sets = [(s, set(s["tokens"]) | tokenize_identifier(s["name"]) | set(s.get("ops", []))) for s in symbols]

    for paper in papers:
        for eq in paper.get("equations", []):
            eq_toks = set(eq.get("tokens", []))
            if not eq_toks:
                continue
            scored = []
            for sym, stoks in sym_sets:
                shared = sorted(eq_toks & stoks)
                if len(shared) < min_overlap:
                    continue
                # Boost matches hitting symbol name tokens directly
                name_toks = tokenize_identifier(sym["name"])
                name_bonus = 1.5 * len(eq_toks & name_toks)
                score = round((len(shared) + name_bonus) / max(3.0, len(eq_toks) ** 0.5), 3)
                scored.append((score, shared, sym))
            scored.sort(key=lambda x: (-x[0], x[2]["file"], x[2]["line"]))
            if scored:
                top_score, shared, sym = scored[0]
                alignments.append({
                    "paper": paper["source"],
                    "equation_id": eq["id"],
                    "equation_loc": f"{eq['file']}:L{eq['line']}",
                    "latex_preview": eq["latex"][:110],
                    "matched_symbol": sym["name"],
                    "symbol_kind": sym["kind"],
                    "code_loc": f"{sym['file']}:L{sym['line']}",
                    "score": top_score,
                    "shared_tokens": shared[:8],
                })
            else:
                unmatched.append({
                    "paper": paper["source"],
                    "equation_id": eq["id"],
                    "equation_loc": f"{eq['file']}:L{eq['line']}",
                    "latex_preview": eq["latex"][:110],
                    "reason": "No AST symbol matched >=2 equation/context tokens (verify implementation exists)",
                })
    return alignments, unmatched


def clone_or_resolve_repo(repo_arg: str, dest_dir: Path) -> Path:
    p = Path(repo_arg)
    if p.exists():
        return p.resolve()
    if repo_arg.startswith(("http://", "https://", "git@")):
        dest_dir.parent.mkdir(parents=True, exist_ok=True)
        if not dest_dir.exists():
            subprocess.run(["git", "clone", "--depth", "1", repo_arg, str(dest_dir)], check=True)
        return dest_dir.resolve()
    raise FileNotFoundError(f"Repository path or URL not found: {repo_arg}")


def write_ingest_markdown(manifest: dict, out_md: Path):
    out_md.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# VeriLoop Ingest Map — Paper Formulas ↔ Codebase AST Alignment",
        "",
        f"- **Generated (UTC):** `{manifest['generated_utc']}`",
        f"- **Papers Ingested:** `{len(manifest['papers'])}`",
        f"- **AST Symbols Indexed:** `{len(manifest['code_symbols'])}`",
        f"- **Formula ↔ Code Alignments:** `{len(manifest['alignments'])}` (Unmatched watchlist: `{len(manifest['unmatched_equations'])}`)",
        "",
        "## 1. Ingested Papers & Extracted Structure",
        "",
    ]
    for p in manifest["papers"]:
        lines.append(f"### `{p['source']}` — {p.get('title', '')}")
        if p.get("authors"):
            lines.append(f"- **Authors:** {', '.join(p['authors'][:6])}" + (" et al." if len(p["authors"]) > 6 else ""))
        if p.get("year"):
            lines.append(f"- **Year:** {p['year']} | **Equations:** `{len(p.get('equations', []))}` | **Sections:** `{len(p.get('sections', []))}`")
        if p.get("github_urls"):
            lines.append(f"- **Linked GitHub Repos:** {', '.join(p['github_urls'][:4])}")
        if p.get("hyperparams"):
            hp_s = "; ".join(f"{h['param']}={','.join(h['values'][:3])}" for h in p["hyperparams"])
            lines.append(f"- **Extracted Hyperparameters:** {hp_s}")
        lines.append("")

    lines.extend([
        "## 2. Formula / Method ↔ Code Alignment Table",
        "",
        "| Paper | Equation ID | LaTeX Location | Matched AST Symbol | Code `file:line` | Score | Shared Tokens |",
        "|---|---|---|---|---|---:|---|",
    ])
    for al in manifest["alignments"]:
        lines.append(
            f"| `{al['paper']}` | `{al['equation_id']}` | `{al['equation_loc']}` | "
            f"`{al['matched_symbol']}` ({al['symbol_kind']}) | `{al['code_loc']}` | "
            f"{al['score']:.2f} | `{', '.join(al['shared_tokens'][:5])}` |"
        )
    if not manifest["alignments"]:
        lines.append("| — | — | — | *(no alignments — provide `--repo` or check unmatched watchlist)* | — | — | — |")

    if manifest["unmatched_equations"]:
        lines.extend([
            "",
            "## 3. Layer-2 Verification Watchlist (Unmatched Equations)",
            "",
            "Equations below had no direct AST symbol match; Layer-2 auditors should verify they are genuinely implemented (not stubbed or omitted):",
            "",
        ])
        for u in manifest["unmatched_equations"][:20]:
            lines.append(f"- `{u['paper']}` `{u['equation_id']}` (`{u['equation_loc']}`): `{u['latex_preview']}`")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", "-w", required=True, help="Target research workspace directory")
    ap.add_argument("--arxiv", nargs="*", default=[], help="arXiv IDs or URLs to download LaTeX source & metadata")
    ap.add_argument("--tex-dir", nargs="*", default=[], help="Local .tex files, directories, or .tar.gz archives")
    ap.add_argument("--repo", default=None, help="Baseline GitHub URL or local Python repo directory to index via AST")
    ap.add_argument("--auto-clone-github", action="store_true", help="Automatically shallow-clone the first GitHub repo discovered in ingested papers if --repo is omitted")
    ap.add_argument("--append-bib", default=None, help="Optional refs.bib path to append canonical BibTeX for ingested arXiv IDs")
    ap.add_argument("--json", action="store_true", help="Print JSON summary to stdout")
    a = ap.parse_args()

    ws = Path(a.workspace).resolve()
    src_root = ws / "ingested/papers"
    src_root.mkdir(parents=True, exist_ok=True)
    papers: list[dict] = []

    # 1. Ingest online arXiv e-print sources
    for raw_id in a.arxiv:
        aid = normalize_arxiv_id(raw_id)
        meta = fetch_arxiv_metadata(aid)
        dest = src_root / aid.replace("/", "_")
        tex_files, err = download_arxiv_source(aid, dest)
        if tex_files:
            parsed = parse_latex_corpus(tex_files, aid)
            if meta.get("title"):
                parsed["title"] = meta["title"]
            parsed.update({k: v for k, v in meta.items() if v and not parsed.get(k)})
            parsed["arxiv_id"] = aid
        else:
            parsed = {
                "source": aid,
                "arxiv_id": aid,
                "title": meta.get("title", aid),
                "authors": meta.get("authors", []),
                "year": meta.get("year", ""),
                "abstract": meta.get("abstract", ""),
                "tex_files": [],
                "sections": [],
                "equations": [],
                "github_urls": sorted(set(GITHUB_URL_RE.findall(meta.get("abstract", "")))),
                "hyperparams": [],
                "source_warning": err,
            }
        papers.append(parsed)

    # 2. Ingest local .tex files / dirs / .tar.gz archives
    for raw_p in a.tex_dir:
        p = Path(raw_p).resolve()
        if not p.exists():
            print(f"ERROR: --tex-dir path not found: {p}", file=sys.stderr)
            sys.exit(2)
        if p.is_file() and p.suffix.lower() in (".gz", ".tar", ".tgz"):
            dest = src_root / p.stem.replace(".tar", "")
            tex_files = _safe_extract_tar_tex(p.read_bytes(), dest)
        elif p.is_file():
            tex_files = [p]
        else:
            tex_files = sorted(p.rglob("*.tex"))
        papers.append(parse_latex_corpus(tex_files, p.name))

    # 3. Resolve / index baseline codebase via AST
    repo_path = None
    repo_target = a.repo
    if not repo_target and a.auto_clone_github:
        for p in papers:
            if p.get("github_urls"):
                repo_target = p["github_urls"][0]
                break
    symbols: list[dict] = []
    if repo_target:
        repo_path = clone_or_resolve_repo(repo_target, ws / "ingested/baseline_repo")
        symbols = index_python_codebase(repo_path)

    # 4. Align formulas <-> AST code
    alignments, unmatched = align_formulas_to_code(papers, symbols)

    manifest = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "workspace": str(ws),
        "repo_indexed": str(repo_path) if repo_path else None,
        "papers": papers,
        "code_symbols": symbols,
        "alignments": alignments,
        "unmatched_equations": unmatched,
    }
    out_json = ws / "out/ingest_manifest.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out_md = ws / "wiki/INGEST_MAP.md"
    write_ingest_markdown(manifest, out_md)

    # Optional: append canonical BibTeX via citation_audit.py
    if a.append_bib and a.arxiv:
        ca_script = Path(__file__).resolve().parents[1] / "skills/research-loop/scripts/citation_audit.py"
        if ca_script.is_file():
            subprocess.run(
                [sys.executable, str(ca_script), "--fetch-bib", *a.arxiv, "--append-to", a.append_bib],
                check=False,
            )

    summary = {
        "status": "OK",
        "papers": len(papers),
        "equations": sum(len(p.get("equations", [])) for p in papers),
        "code_symbols": len(symbols),
        "alignments": len(alignments),
        "unmatched_equations": len(unmatched),
        "manifest": str(out_json),
        "wiki_map": str(out_md),
    }
    if a.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"INGEST OK | papers={summary['papers']} equations={summary['equations']} "
            f"ast_symbols={summary['code_symbols']} alignments={summary['alignments']} "
            f"unmatched={summary['unmatched_equations']} -> {out_md}"
        )


if __name__ == "__main__":
    main()
