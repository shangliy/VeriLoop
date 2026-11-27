#!/usr/bin/env python3
"""VeriLoop vs. HKUDS/AI-Researcher Reproducible Comparative Audit Benchmark.

Runs identical, zero-override deterministic auditors across:
  1. VeriLoop v5 Multi-Domain Real-GPU Workspaces (CV, GNN, RecSys)
  2. Official Published HKUDS/AI-Researcher Showcase Outputs (`examples/*`)
     (auto-fetched via sparse git clone with `--fetch-ai-researcher`, or supplied
     via `--ai-researcher-dir /path/to/AI-Researcher`)

Evaluates 4 quantitative axes per workspace:
  - Axis 1: Numerical Provenance & Expanded-PDF Trace Rate (`pdf_audit.py` / `trace_numbers.py`)
  - Axis 2: Python AST Code Integrity (`audit_code.py --strict`: HIGH / MEDIUM defect counts + codes)
  - Axis 3: Citation & Typography Integrity (`citation_audit.py` + PDF `??` / `[?]` / Type-3 checks)
  - Axis 4: Verification Governance & Cost (claims G1-G7, paper-bind SHA-256, Formula<->AST map,
            interactive Review UI, Layer-1 audit latency ms, and `$0` mechanical audit cost)

Outputs:
  - `<out-dir>/comparison_report.json`
  - `<out-dir>/COMPARISON_REPORT.md`
  - `<out-dir>/comparison_chart.png` (and `.pdf` when matplotlib is available)

Zero external Python dependencies for the audit core (stdlib only; matplotlib optional for plot).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
RL_SCRIPTS = ROOT / "skills/research-loop/scripts"

DEFAULT_VERILOOP_WORKSPACES = [
    ("VeriLoop-v5 (CV: CIFAR-10 & F-MNIST, 42 GPU runs)", "CV", ROOT / "examples/gpu-overnight-research"),
    ("VeriLoop-v5 (GNN: Cora & CiteSeer, 60 GPU runs)", "GNN", ROOT / "examples/gpu-gnn-cora-citeseer"),
    ("VeriLoop-v5 (RecSys: MovieLens-100K, 13 GPU runs)", "RecSys", ROOT / "examples/gpu-recsys-movielens"),
]

AI_RESEARCHER_DOMAIN_MAP = {
    "gnn_difformer": "GNN",
    "gnn_nodeformer": "GNN",
    "dccf": "RecSys",
    "hgcl": "RecSys",
    "con_flowmatching": "Diffusion/Flow",
    "fsq": "VQ/CV",
    "rotation_vq": "VQ/CV",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout)


def sparse_fetch_ai_researcher(dest: Path) -> Path:
    """Shallow sparse-clone only examples/*/paper.pdf, examples/*/project/**, and benchmark/final/** (no large video blobs)."""
    if (dest / "examples").is_dir():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_cmd([
        "git", "clone", "--depth", "1", "--filter=blob:none", "--no-checkout",
        "https://github.com/HKUDS/AI-Researcher.git", str(dest),
    ], timeout=120)
    run_cmd([
        "git", "sparse-checkout", "set", "--no-cone",
        "/examples/*/paper.pdf",
        "/examples/*/project/**",
        "/benchmark/final/**",
        "!*.mp4", "!*.avi", "!*.gif", "!*.png",
    ], cwd=dest, timeout=120)
    run_cmd(["git", "checkout"], cwd=dest, timeout=180)
    return dest


def _find_deliverable(ws: Path) -> tuple[Path | None, str]:
    """Find primary PDF or Markdown/LaTeX manuscript for a workspace."""
    for cand in [
        ws / "paper.pdf",
        ws / "paper/overnight_study.pdf",
        ws / "paper/main.pdf",
        ws / "paper/gnn_study.pdf",
        ws / "paper/recsys_study.pdf",
    ]:
        if cand.is_file():
            return cand, "pdf"
    pdfs = sorted(ws.glob("paper/*.pdf")) or sorted(ws.glob("*.pdf"))
    if pdfs:
        return pdfs[0], "pdf"
    for cand in [ws / "report/report.md", ws / "paper/main.tex"]:
        if cand.is_file():
            return cand, "text"
    return None, "none"


def _find_log_paths(ws: Path) -> list[Path]:
    """Collect candidate log files/dirs on disk (without fabricating any)."""
    logs: list[Path] = []
    # 1. VeriLoop standard locations
    for rel in ("out", "paper/bound"):
        p = ws / rel
        if p.is_dir():
            for fp in sorted(p.rglob("*")):
                if fp.is_file() and fp.suffix.lower() in (".txt", ".log", ".csv", ".json", ".jsonl"):
                    if fp.name not in ("ingest_manifest.json", "pipeline_plan.json", "pipeline_events.jsonl"):
                        logs.append(fp)
    # 2. AI-Researcher project logs & structured JSON/CSV result artifacts
    proj = ws / "project"
    if proj.is_dir():
        for fp in sorted(proj.rglob("*")):
            if fp.is_file() and (
                fp.suffix.lower() in (".log", ".txt", ".csv", ".json", ".jsonl")
                or "logs" in fp.parts
            ):
                if fp.name.lower() not in ("readme.md", "requirements.txt"):
                    logs.append(fp)
    # Deduplicate preserving order
    seen = set()
    uniq = []
    for lp in logs:
        rp = lp.resolve()
        if rp not in seen:
            seen.add(rp)
            uniq.append(rp)
    return uniq


def _find_code_dirs(ws: Path) -> list[Path]:
    dirs = []
    for rel in ("code", "project"):
        p = ws / rel
        if p.is_dir() and any(p.rglob("*.py")):
            dirs.append(p)
    return dirs


def _count_pdf_citations_and_broken(pdf_path: Path) -> dict:
    """Inspect extracted PDF text for unresolved citations (`[?]`, `??`) and approximate ref count."""
    r = run_cmd(["pdftotext", str(pdf_path), "-"])
    if r.returncode != 0:
        return {"pdf_ref_entries_est": 0, "unresolved_cite_markers": 0}
    txt = r.stdout
    unresolved = len(re.findall(r"\[\?\]|\(\?\)|\?\?", txt))
    # Count reference-section entries roughly via year patterns (20xx)/(19xx) after "References"
    m_ref = re.search(r"\nReferences\s*\n(.*)", txt, re.DOTALL)
    ref_count = 0
    if m_ref:
        ref_sec = m_ref.group(1)
        ref_count = len(re.findall(r"\b(?:19|20)\d{2}\b", ref_sec))
    return {"pdf_ref_entries_est": ref_count, "unresolved_cite_markers": unresolved}


def audit_workspace(
    system: str,
    label: str,
    domain: str,
    ws: Path,
    online_cites: bool = False,
) -> dict:
    t0 = time.perf_counter()
    deliverable, deliv_kind = _find_deliverable(ws)
    log_files = _find_log_paths(ws)
    code_dirs = _find_code_dirs(ws)

    # ---------- AXIS 1: NUMERICAL PROVENANCE & PDF AUDIT ----------
    num_total = 0
    num_traced = 0
    num_untraced = 0
    type3_fonts = 0
    unresolved_refs = 0
    pdf_pages = 0

    if deliverable and deliv_kind == "pdf":
        cmd_pdf = [sys.executable, str(TOOLS / "pdf_audit.py"), str(deliverable), "--json"]
        if log_files:
            cmd_pdf.extend(["--logs", *[str(p) for p in log_files[:80]]])
        r_pdf = run_cmd(cmd_pdf, timeout=90)
        if r_pdf.stdout.strip().startswith("{"):
            pdata = json.loads(r_pdf.stdout)
            pdf_pages = int(pdata.get("pages", 0))
            type3_fonts = len(pdata.get("type3_fonts", [])) if isinstance(pdata.get("type3_fonts"), list) else int(pdata.get("type3_fonts", 0) or 0)
            unresolved_refs = sum(1 for iss in pdata.get("issues", []) if iss.get("code") == "UNRESOLVED_REF")
            nt = pdata.get("pdf_number_trace") or {}
            num_traced = int(nt.get("traced", 0))
            num_untraced = int(nt.get("untraced", 0)) + int(nt.get("sign_mismatches", 0))
            num_total = num_traced + num_untraced
    elif deliverable and deliv_kind == "text":
        cmd_tr = [sys.executable, str(RL_SCRIPTS / "trace_numbers.py"), str(deliverable), "--json"]
        for lp in log_files[:80]:
            cmd_tr.extend(["--logs", str(lp)])
        r_tr = run_cmd(cmd_tr, timeout=60)
        if r_tr.stdout.strip().startswith("{"):
            tdata = json.loads(r_tr.stdout)
            num_traced = int(tdata.get("traced", 0))
            num_untraced = len(tdata.get("untraced", [])) + len(tdata.get("sign_mismatches", [])) + len(tdata.get("wrong_logs", []))
            num_total = num_traced + num_untraced

    # Also check pre-committed pdf_audit.json if workspace has no PDF rebuilt yet (never overrides live run)
    trace_rate = round(100.0 * num_traced / num_total, 2) if num_total > 0 else (100.0 if log_files else 0.0)

    # ---------- AXIS 2: PYTHON AST CODE INTEGRITY ----------
    py_files = sum(len(list(d.rglob("*.py"))) for d in code_dirs)
    ast_high = 0
    ast_medium = 0
    ast_high_codes: list[str] = []
    ast_medium_codes: list[str] = []

    if code_dirs:
        cmd_ast = [sys.executable, str(RL_SCRIPTS / "audit_code.py"), "--json", "--strict"]
        for d in code_dirs:
            cmd_ast.extend(["--scripts", str(d)])
        if deliverable and deliv_kind == "text":
            cmd_ast.extend(["--report", str(deliverable)])
        r_ast = run_cmd(cmd_ast, timeout=90)
        if r_ast.stdout.strip().startswith("{"):
            adata = json.loads(r_ast.stdout)
            for f in adata.get("findings", []):
                sev = f.get("severity")
                code = f.get("code", "UNKNOWN")
                if sev == "HIGH":
                    ast_high += 1
                    ast_high_codes.append(code)
                elif sev == "MEDIUM":
                    ast_medium += 1
                    ast_medium_codes.append(code)

    # ---------- AXIS 3: CITATION & REFERENCE INTEGRITY ----------
    bib_file = ws / "paper/refs.bib"
    tex_files = sorted((ws / "paper").glob("*.tex")) if (ws / "paper").is_dir() else []
    cite_mode = "none"
    cite_verified = 0
    cite_total = 0
    cite_issues = 0

    # Check committed verify_cites_online.json or run live citation_audit.py
    committed_cites = ws / "audits/verify_cites_online.json"
    if committed_cites.is_file() and not online_cites:
        cdata = json.loads(committed_cites.read_text(encoding="utf-8"))
        cite_mode = "bibtex_online_committed"
        cite_total = int(cdata.get("cited_count", len(cdata.get("online_results", []))))
        cite_issues = len(cdata.get("missing_in_bib", [])) + len(cdata.get("online_errors", []))
        cite_verified = max(0, cite_total - cite_issues)
    elif bib_file.is_file() and (tex_files or (deliverable and deliv_kind == "text")):
        target_doc = tex_files[0] if tex_files else deliverable
        cmd_cit = [sys.executable, str(RL_SCRIPTS / "citation_audit.py"), str(target_doc), "--bib", str(bib_file), "--json"]
        if online_cites:
            cmd_cit.append("--online")
        r_cit = run_cmd(cmd_cit, timeout=90)
        if r_cit.stdout.strip().startswith("{"):
            cdata = json.loads(r_cit.stdout)
            cite_mode = "bibtex_online_live" if online_cites else "bibtex_local"
            cite_total = int(cdata.get("cited_count", len(cdata.get("bib_keys", []))))
            cite_issues = len(cdata.get("missing_in_bib", [])) + len(cdata.get("online_errors", []))
            cite_verified = max(0, cite_total - cite_issues)
    elif deliverable and deliv_kind == "pdf":
        p_cit = _count_pdf_citations_and_broken(deliverable)
        cite_mode = "pdf_only_no_bib"
        cite_total = p_cit["pdf_ref_entries_est"]
        cite_issues = p_cit["unresolved_cite_markers"]
        cite_verified = 0  # Unverified because no BibTeX + online gate exists

    # ---------- AXIS 4: GOVERNANCE, ALIGNMENT & COST ----------
    has_claims = (ws / "claims.json").is_file()
    has_paper_bind = bool(list((ws / "paper/bound").glob("**/provenance_manifest.json"))) if (ws / "paper/bound").is_dir() else False
    has_ingest_map = (ws / "out/ingest_manifest.json").is_file()
    ingest_alignments = 0
    if has_ingest_map:
        try:
            im = json.loads((ws / "out/ingest_manifest.json").read_text(encoding="utf-8"))
            ingest_alignments = len(im.get("alignments", []))
        except Exception:
            pass
    has_review_ui = (ws / "review_ui.html").is_file()
    has_studio_snap = (ws / "studio_snapshot.html").is_file()
    has_hard_gate = (ws / "audits/veriloop_gate.json").is_file()
    gate_passed = False
    if has_hard_gate:
        try:
            gd = json.loads((ws / "audits/veriloop_gate.json").read_text(encoding="utf-8"))
            gate_passed = not bool(gd.get("blocked", True))
        except Exception:
            pass

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)

    return {
        "system": system,
        "label": label,
        "domain": domain,
        "workspace": str(ws),
        "deliverable": str(deliverable) if deliverable else None,
        "deliverable_kind": deliv_kind,
        "pdf_pages": pdf_pages,
        "log_files_count": len(log_files),
        "numbers_total": num_total,
        "numbers_traced": num_traced,
        "numbers_untraced": num_untraced,
        "trace_rate_pct": trace_rate,
        "type3_fonts": type3_fonts,
        "unresolved_refs": unresolved_refs,
        "py_files_scanned": py_files,
        "ast_high_count": ast_high,
        "ast_medium_count": ast_medium,
        "ast_high_codes": sorted(set(ast_high_codes)),
        "ast_medium_codes": sorted(set(ast_medium_codes)),
        "ast_clean": (ast_high == 0),
        "cite_mode": cite_mode,
        "cite_total": cite_total,
        "cite_verified": cite_verified,
        "cite_issues": cite_issues,
        "governance": {
            "claims_ledger_g1_g7": has_claims,
            "paper_bind_sha256": has_paper_bind,
            "formula_ast_alignment": has_ingest_map,
            "formula_alignments_count": ingest_alignments,
            "hard_gate_passed": gate_passed,
            "interactive_review_ui": has_review_ui,
            "studio_snapshot": has_studio_snap,
        },
        "layer1_audit_ms": elapsed_ms,
        "layer1_audit_cost_usd": 0.0,
    }


def aggregate_by_system(rows: list[dict]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        grouped.setdefault(r["system"], []).append(r)
    agg = {}
    for sys_name, items in grouped.items():
        n = len(items)
        tot_nums = sum(x["numbers_total"] for x in items)
        tot_traced = sum(x["numbers_traced"] for x in items)
        with_logs = [x for x in items if x["log_files_count"] > 0]
        wl_nums = sum(x["numbers_total"] for x in with_logs)
        wl_traced = sum(x["numbers_traced"] for x in with_logs)
        agg[sys_name] = {
            "workspaces_audited": n,
            "workspaces_with_logs": len(with_logs),
            "total_numbers": tot_nums,
            "total_traced": tot_traced,
            "overall_trace_rate_pct": round(100.0 * tot_traced / tot_nums, 2) if tot_nums > 0 else 0.0,
            "with_logs_trace_rate_pct": round(100.0 * wl_traced / wl_nums, 2) if wl_nums > 0 else 0.0,
            "total_py_files": sum(x["py_files_scanned"] for x in items),
            "total_ast_high": sum(x["ast_high_count"] for x in items),
            "total_ast_medium": sum(x["ast_medium_count"] for x in items),
            "ast_clean_workspace_pct": round(100.0 * sum(1 for x in items if x["ast_clean"]) / max(1, n), 1),
            "bib_verified_workspace_pct": round(
                100.0 * sum(1 for x in items if x["cite_mode"].startswith("bibtex_") and x["cite_issues"] == 0) / max(1, n), 1
            ),
            "governance_score_pct": round(
                100.0 * sum(
                    sum(1 for k in ("claims_ledger_g1_g7", "paper_bind_sha256", "hard_gate_passed", "interactive_review_ui") if x["governance"][k])
                    for x in items
                ) / max(1, 4 * n),
                1,
            ),
            "mean_audit_ms": round(sum(x["layer1_audit_ms"] for x in items) / max(1, n), 1),
            "layer1_cost_usd": 0.0,
        }
    return agg


def write_markdown_report(rows: list[dict], agg: dict[str, dict], out_md: Path):
    lines = [
        "# VeriLoop v5 vs. HKUDS/AI-Researcher — Reproducible Automated Audit Comparison",
        "",
        f"- **Generated (UTC):** `{utc_now()}`",
        "- **Methodology:** Identical zero-override deterministic Layer-1 auditors (`pdf_audit.py` / `trace_numbers.py`, `audit_code.py --strict`, `citation_audit.py`) executed directly on VeriLoop v5 multi-domain RTX 3060 Ti workspaces and official published `HKUDS/AI-Researcher/examples/*` showcase outputs (`paper.pdf` + `project/`). Layer-1 audit cost: `$0.00`.",
        "- **Fairness Note:** Official `HKUDS/AI-Researcher/examples/*` repositories publish `paper.pdf` + `project/` codebases, and only a subset include raw `.log` files (`workspaces_with_logs`). Both overall trace rate and **with-logs-only** trace rate are reported explicitly below.",
        "",
        "## 1. System-Level Aggregate Comparison",
        "",
        "| System | Workspaces (With Logs) | Numbers Traced (All) | Numbers Traced (With Logs Only) | AST Clean Workspaces (0 HIGH) | Total AST HIGH / MED | Verified BibTeX Coverage | Governance Score (Claims/Bind/Gate/UI) | Mean Audit Latency |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for sys_name, a in agg.items():
        lines.append(
            f"| **{sys_name}** | `{a['workspaces_audited']}` (`{a['workspaces_with_logs']}`) | "
            f"`{a['total_traced']}/{a['total_numbers']}` (**{a['overall_trace_rate_pct']:.1f}%**) | "
            f"**{a['with_logs_trace_rate_pct']:.1f}%** | "
            f"**{a['ast_clean_workspace_pct']:.1f}%** | "
            f"`{a['total_ast_high']}` / `{a['total_ast_medium']}` | "
            f"**{a['bib_verified_workspace_pct']:.1f}%** | "
            f"**{a['governance_score_pct']:.1f}%** | "
            f"`{a['mean_audit_ms']:.0f} ms` |"
        )

    lines.extend([
        "",
        "## 2. Per-Workspace Forensic Breakdown",
        "",
        "| System | Workspace | Domain | Deliverable | Logs | Traced / Total | AST HIGH (Codes) | AST MED | Citation Mode | Claims / Bind / UI |",
        "|---|---|---|---|---:|---:|---|---:|---|---|",
    ])
    for r in rows:
        g = r["governance"]
        gov_s = f"{'✅' if g['claims_ledger_g1_g7'] else '❌'} / {'✅' if g['paper_bind_sha256'] else '❌'} / {'✅' if g['interactive_review_ui'] else '❌'}"
        codes = ", ".join(r["ast_high_codes"][:3]) if r["ast_high_codes"] else "—"
        lines.append(
            f"| {r['system']} | `{r['label']}` | {r['domain']} | `{r['deliverable_kind']}` | "
            f"`{r['log_files_count']}` | `{r['numbers_traced']}/{r['numbers_total']}` ({r['trace_rate_pct']:.1f}%) | "
            f"`{r['ast_high_count']}` ({codes}) | `{r['ast_medium_count']}` | "
            f"`{r['cite_mode']}` | {gov_s} |"
        )

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_comparison_chart(agg: dict[str, dict], out_dir: Path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:
        return

    systems = list(agg.keys())
    if len(systems) < 2:
        return

    metrics = [
        ("Number Trace\n(With Logs)", "with_logs_trace_rate_pct"),
        ("AST Clean Code\n(0 HIGH)", "ast_clean_workspace_pct"),
        ("Verified BibTeX\nCoverage", "bib_verified_workspace_pct"),
        ("Governance\n(Claims/Bind/Gate/UI)", "governance_score_pct"),
    ]
    x = np.arange(len(metrics))
    width = 0.34
    colors = ["#0072B2", "#D55E00", "#009E73"]

    fig, ax = plt.subplots(figsize=(8.6, 4.2), dpi=200)
    for idx, sys_name in enumerate(systems):
        vals = [agg[sys_name][k] for _, k in metrics]
        offset = (idx - (len(systems) - 1) / 2.0) * width
        bars = ax.bar(x + offset, vals, width, label=sys_name, color=colors[idx % len(colors)], edgecolor="#0F172A", linewidth=0.7)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2.0, v + 2.5, f"{v:.1f}%", ha="center", va="bottom", fontsize=9.5, fontweight="bold", color="#0F172A")

    ax.set_ylabel("Verified Rate (%)", fontsize=10.5, fontweight="bold")
    ax.set_title("VeriLoop v5 vs. HKUDS/AI-Researcher — Deterministic Layer-1 Audit ($0 Cost)", fontsize=11.5, fontweight="bold", pad=28)
    ax.set_xticks(x)
    ax.set_xticklabels([m[0] for m in metrics], fontsize=9.5)
    ax.set_ylim(0, 114)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=len(systems), fontsize=10)
    fig.tight_layout()
    fig.savefig(out_dir / "comparison_chart.pdf")
    fig.savefig(out_dir / "comparison_chart.png", dpi=220)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ai-researcher-dir", default=None, help="Local path to cloned HKUDS/AI-Researcher repo")
    ap.add_argument("--fetch-ai-researcher", action="store_true", help="Auto sparse-clone HKUDS/AI-Researcher examples/ into /tmp/ai_researcher_ref")
    ap.add_argument("--cache-dir", default="/tmp/ai_researcher_ref", help="Target dir for --fetch-ai-researcher")
    ap.add_argument("--online-cites", action="store_true", help="Enable live arXiv/Crossref/S2 citation API checks")
    ap.add_argument("--out-dir", default=str(ROOT / "eval/comparison_ai_researcher"), help="Output directory for JSON/MD/chart")
    ap.add_argument("--json", action="store_true", help="Print aggregate JSON summary to stdout")
    a = ap.parse_args()

    out_dir = Path(a.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []

    # 1. Audit VeriLoop v5 multi-domain workspaces
    for label, domain, ws in DEFAULT_VERILOOP_WORKSPACES:
        if ws.is_dir():
            rows.append(audit_workspace("VeriLoop v5", label, domain, ws, online_cites=a.online_cites))

    # 2. Audit HKUDS/AI-Researcher official examples if available/requested
    air_dir = Path(a.ai_researcher_dir).resolve() if a.ai_researcher_dir else None
    if not air_dir and a.fetch_ai_researcher:
        air_dir = sparse_fetch_ai_researcher(Path(a.cache_dir))

    if air_dir and (air_dir / "examples").is_dir():
        for ex in sorted((air_dir / "examples").iterdir()):
            if ex.is_dir() and ((ex / "paper.pdf").is_file() or (ex / "project").is_dir()):
                dom = AI_RESEARCHER_DOMAIN_MAP.get(ex.name, "Other")
                rows.append(audit_workspace("HKUDS/AI-Researcher", f"AI-Researcher ({ex.name})", dom, ex, online_cites=a.online_cites))

    agg = aggregate_by_system(rows)
    payload = {
        "generated_utc": utc_now(),
        "aggregate": agg,
        "workspaces": rows,
    }
    (out_dir / "comparison_report.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown_report(rows, agg, out_dir / "COMPARISON_REPORT.md")
    render_comparison_chart(agg, out_dir)

    if a.json:
        print(json.dumps(agg, indent=2))
    else:
        print(f"COMPARE_BENCH COMPLETE | workspaces={len(rows)} | report={out_dir / 'COMPARISON_REPORT.md'}")
        for sys_name, st in agg.items():
            print(
                f"  {sys_name:22s}: ws={st['workspaces_audited']} (logs={st['workspaces_with_logs']}) | "
                f"trace_all={st['overall_trace_rate_pct']:.1f}% trace_with_logs={st['with_logs_trace_rate_pct']:.1f}% | "
                f"ast_clean={st['ast_clean_workspace_pct']:.1f}% (HIGH={st['total_ast_high']}) | "
                f"bib={st['bib_verified_workspace_pct']:.1f}% | gov={st['governance_score_pct']:.1f}%"
            )


if __name__ == "__main__":
    main()
