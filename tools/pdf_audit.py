#!/usr/bin/env python3
"""VeriLoop Per-Page PDF Layout, Visual Margin & Expanded-Macro Auditor (stdlib-only + poppler).

Audits a compiled conference PDF (arXiv / ICML / NeurIPS / ICLR / ACL / SIGIR) end to end:
  1. Page count & main-body page limit check (before References / Impact / Appendix).
  2. Embedded font hygiene (blocks Type-3 bitmap fonts rejected by camera-ready systems).
  3. Unresolved LaTeX reference/citation markers (`??`, `[?]`) & near-blank pages.
  4. Optional double-blind anonymity leak scan (`--forbidden-terms ...`).
  5. Optional LaTeX `.log` `Overfull \\hbox` (>10pt) check when sibling `.log` exists.
  6. Per-page PNG rendering (`--render-dir`, via `pdftoppm`) + optional pixel edge-margin
     ink-overflow check (if Pillow is installed) to catch overflowing tables/equations visually.
  7. Expanded-macro numerical provenance (`--logs ...`): runs `trace_numbers.py` on the
     final compiled PDF text (after LaTeX macros expand!) against raw execution logs.

Usage:
  pdf_audit.py paper/main_icml2027.pdf --max-main-pages 8 --forbidden-terms "Shanglin" "Zhan Shi" "shangliy"
  pdf_audit.py examples/gpu-dl-benchmark/paper/gpu_showcase.pdf --logs examples/gpu-dl-benchmark/paper/bound/bound_metrics.txt examples/gpu-dl-benchmark/out/gpu_runs.log --render-dir /tmp/gpu_pages
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RL_SCRIPTS = REPO_ROOT / "skills/research-loop/scripts"

BACKMATTER_RE = re.compile(
    r"^\s*(?:AI Use Statement|Impact Statement|Broader Impact|Ethics Statement|References|Bibliography|Appendix(?:\s+[A-Z0-9.:-]+.*)?)\s*$",
    re.M,
)
UNRESOLVED_RE = re.compile(r"(?:\[\?\]|\(\?\)|(?<![\w?])\?\?(?![\w?]))")
OVERFULL_RE = re.compile(r"Overfull \\hbox \(([0-9.]+)pt too wide\)")


def _run(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def audit_pdf(
    pdf_path: Path,
    max_main_pages: int | None = None,
    forbidden_terms: list[str] | None = None,
    log_paths: list[Path] | None = None,
    render_dir: Path | None = None,
    dpi: int = 120,
    edge_margin_px: int = 10,
) -> dict:
    issues = []
    warnings = []
    info = {"pdf": str(pdf_path), "pages": 0, "main_body_end_page": None, "type3_fonts": [], "rendered_pages": []}

    if not pdf_path.is_file():
        return {"error": f"PDF not found: {pdf_path}", "issues": [{"severity": "HIGH", "code": "MISSING_PDF"}], "warnings": []}

    # 1. Page count via pdfinfo
    if shutil.which("pdfinfo"):
        rc, out, _ = _run(["pdfinfo", str(pdf_path)])
        m = re.search(r"Pages:\s+(\d+)", out)
        if m:
            info["pages"] = int(m.group(1))

    # 2. Type-3 font check via pdffonts
    if shutil.which("pdffonts"):
        rc, out, _ = _run(["pdffonts", str(pdf_path)])
        for line in out.splitlines()[2:]:
            if re.search(r"\bType\s+3\b", line, re.I):
                info["type3_fonts"].append(line.strip())
        if info["type3_fonts"]:
            issues.append({
                "severity": "HIGH", "code": "TYPE3_FONT",
                "detail": f"Found {len(info['type3_fonts'])} Type-3 bitmap font(s): {info['type3_fonts'][:3]}",
            })

    # 3. Per-page text extraction via pdftotext
    pages_text = []
    if shutil.which("pdftotext") and info["pages"] > 0:
        for pg in range(1, info["pages"] + 1):
            _, ptxt, _ = _run(["pdftotext", "-f", str(pg), "-l", str(pg), str(pdf_path), "-"])
            pages_text.append((pg, ptxt))
            words = re.findall(r"[A-Za-z]{2,}", ptxt)
            if len(words) < 15:
                warnings.append({
                    "severity": "MEDIUM", "code": "SPARSE_OR_BLANK_PAGE", "page": pg,
                    "detail": f"Page {pg} has only {len(words)} words (check for stray page break)",
                })
            if UNRESOLVED_RE.search(ptxt):
                issues.append({
                    "severity": "HIGH", "code": "UNRESOLVED_LATEX_REF", "page": pg,
                    "detail": f"Unresolved LaTeX reference/citation marker (`??` or `[?]`) on page {pg}",
                })
            bm = BACKMATTER_RE.search(ptxt)
            if info["main_body_end_page"] is None and bm:
                # If backmatter begins near the top of the page (e.g. after \newpage), main body ended on pg - 1;
                # if substantial main text precedes References on the same page, main body ends on pg.
                prefix_words = len(re.findall(r"[A-Za-z]{2,}", ptxt[:bm.start()]))
                info["main_body_end_page"] = (pg - 1) if (pg > 1 and prefix_words < 40) else pg

        if info["main_body_end_page"] is None:
            info["main_body_end_page"] = info["pages"]

        if max_main_pages is not None and info["main_body_end_page"] > max_main_pages:
            issues.append({
                "severity": "HIGH", "code": "MAIN_PAGE_LIMIT_EXCEEDED",
                "detail": f"Main body reaches page {info['main_body_end_page']} (limit: {max_main_pages})",
            })

        # 4. Double-blind anonymity check
        if forbidden_terms:
            full_txt = "\n".join(t for _, t in pages_text)
            for term in forbidden_terms:
                if not term:
                    continue
                if re.search(re.escape(term), full_txt, re.I):
                    issues.append({
                        "severity": "HIGH", "code": "ANONYMITY_LEAK",
                        "detail": f"Forbidden/identifying term '{term}' found in compiled PDF",
                    })

    # 5. Sibling LaTeX .log Overfull hbox check
    tex_log = pdf_path.with_suffix(".log")
    if tex_log.is_file():
        overfulls = []
        for m in OVERFULL_RE.finditer(tex_log.read_text(encoding="utf-8", errors="replace")):
            pts = float(m.group(1))
            if pts >= 10.0:
                overfulls.append(pts)
        if overfulls:
            warnings.append({
                "severity": "MEDIUM", "code": "OVERFULL_HBOX",
                "detail": f"{len(overfulls)} Overfull \\hbox >= 10pt (max={max(overfulls):.1f}pt) in {tex_log.name}",
            })

    # 6. Per-page PNG rendering & optional visual margin-ink overflow check
    if render_dir is not None and shutil.which("pdftoppm"):
        render_dir.mkdir(parents=True, exist_ok=True)
        prefix = render_dir / pdf_path.stem
        _run(["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), str(prefix)])
        pngs = sorted(render_dir.glob(f"{pdf_path.stem}-*.png"))
        info["rendered_pages"] = [str(p) for p in pngs]
        try:
            from PIL import Image  # optional visual margin check

            for p in pngs:
                im = Image.open(p).convert("L")
                w, h = im.size
                # Check if dark ink (< 200 gray) touches extreme left/right edges (table/eq overflow)
                left_box = im.crop((0, int(h * 0.08), edge_margin_px, int(h * 0.92)))
                right_box = im.crop((w - edge_margin_px, int(h * 0.08), w, int(h * 0.92)))
                if left_box.getextrema()[0] < 180 or right_box.getextrema()[0] < 180:
                    warnings.append({
                        "severity": "MEDIUM", "code": "VISUAL_EDGE_OVERFLOW",
                        "detail": f"Ink detected within {edge_margin_px}px of horizontal page edge in {p.name}",
                    })
        except ImportError:
            pass

    # 7. Expanded-macro numerical provenance check on compiled PDF text
    if log_paths and pages_text:
        # Exclude References/Bibliography onwards (DOIs/years/arXiv IDs) while keeping main text on the same page
        chunks = []
        for pg, t in pages_text:
            bm = BACKMATTER_RE.search(t)
            if bm:
                chunks.append(t[:bm.start()])
                break
            chunks.append(t)
        main_txt = "\n".join(chunks)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tf:
            tf.write(main_txt)
            tmp_txt = Path(tf.name)
        try:
            cmd = [sys.executable, str(RL_SCRIPTS / "trace_numbers.py"), str(tmp_txt), "--json"]
            for lp in log_paths:
                cmd.extend(["--logs", str(lp)])
            rc, out, _ = _run(cmd)
            if out.strip().startswith("{"):
                tr = json.loads(out)
                info["pdf_number_trace"] = {
                    "traced": tr.get("traced", 0),
                    "untraced": len(tr.get("untraced", [])),
                    "sign_mismatches": len(tr.get("sign_mismatches", [])),
                    "untraced_samples": [u["number"] for u in tr.get("untraced", [])[:10]],
                }
                if tr.get("untraced") or tr.get("sign_mismatches"):
                    warnings.append({
                        "severity": "MEDIUM", "code": "PDF_EXPANDED_UNTRACED",
                        "detail": (
                            f"Compiled PDF main-body text has {len(tr.get('untraced', []))} untraced "
                            f"and {len(tr.get('sign_mismatches', []))} sign-mismatched decimals "
                            f"(samples: {[u['number'] for u in tr.get('untraced', [])[:5]]})"
                        ),
                    })
        finally:
            tmp_txt.unlink(missing_ok=True)

    return {**info, "issues_count": len(issues), "warnings_count": len(warnings), "issues": issues, "warnings": warnings}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", help="Compiled PDF file to audit")
    ap.add_argument("--max-main-pages", type=int, default=None, help="Maximum allowed main-body pages (e.g. 8 for ICML)")
    ap.add_argument("--forbidden-terms", nargs="*", default=[], help="Terms that must NOT appear (double-blind anonymity check)")
    ap.add_argument("--logs", nargs="*", default=[], help="Optional raw log file(s)/dir(s) for expanded-macro PDF number tracing")
    ap.add_argument("--render-dir", default=None, help="Optional directory to render per-page PNG screenshots for visual inspection")
    ap.add_argument("--dpi", type=int, default=120, help="PNG render DPI (default: 120)")
    ap.add_argument("--strict-warnings", action="store_true", help="Exit 1 on MEDIUM warnings too")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    res = audit_pdf(
        Path(a.pdf).resolve(),
        max_main_pages=a.max_main_pages,
        forbidden_terms=a.forbidden_terms,
        log_paths=[Path(p).resolve() for p in a.logs] if a.logs else None,
        render_dir=Path(a.render_dir).resolve() if a.render_dir else None,
        dpi=a.dpi,
    )
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        status = "FAILED" if (res["issues_count"] > 0 or (a.strict_warnings and res["warnings_count"] > 0)) else "PASSED"
        print(
            f"PDF_AUDIT: {status} | {a.pdf} | pages={res['pages']} main_end={res['main_body_end_page']} "
            f"| type3={len(res['type3_fonts'])} | issues={res['issues_count']} warnings={res['warnings_count']}"
        )
        if "pdf_number_trace" in res:
            pt = res["pdf_number_trace"]
            print(f"  expanded_pdf_numbers: traced={pt['traced']} untraced={pt['untraced']} sign={pt['sign_mismatches']}")
        if res["rendered_pages"]:
            print(f"  rendered_pngs: {len(res['rendered_pages'])} pages -> {a.render_dir}")
        for iss in res["issues"]:
            print(f"  [HIGH] {iss['code']}: {iss['detail']}")
        for w in res["warnings"]:
            print(f"  [WARN] {w['code']}: {w['detail']}")
    failed = res["issues_count"] > 0 or (a.strict_warnings and res["warnings_count"] > 0)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
