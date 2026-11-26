#!/usr/bin/env python3
"""Unified Verifiable-ARIS Hard Evidence Gate CLI.

Bridges ARIS research workspaces (experiment-audit, result-to-claim,
paper-claim-audit, research-pipeline) with Verifiable Research-Loop's
zero-dependency dual-layer governance stack:

  Layer 1 (Deterministic, $0 LLM cost):
    - trace_numbers.py : signed numerical provenance, WRONG_LOG, UNPAIRED_PM/CI, staleness
    - audit_code.py    : 6 Python AST integrity checks (hardcoded prints, mock fallbacks, test tuning, ...)
    - citation_audit.py: optional LaTeX/BibTeX verification when --bib is supplied
    - claims.py        : optional G1-G7 ledger verification when claims.json exists

  Layer 2 (Optional Path-Isolated Cross-Model Hard Blocking):
    - run_audit.py     : strips all executor summaries, passes raw paths + pre-audit JSON only,
                         and enforces hard blocking on BLOCK_MISCONDUCT / BLOCK_UNSUPPORTED.

Exit codes:
  0  All enabled gates PASSED (delivery allowed)
  2  Hard BLOCK triggered (mechanical failure or reviewer BLOCK_* verdict)
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RL_SCRIPTS = REPO_ROOT / "skills/research-loop/scripts"


def run_cmd(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", "-w", default=".", help="Project workspace root")
    ap.add_argument("--report", required=True, help="Report/manuscript path (relative to workspace or absolute)")
    ap.add_argument("--logs", nargs="+", required=True, help="Raw log file(s) or directory(ies)")
    ap.add_argument("--scripts", nargs="*", default=[], help="Code file(s) or directory(ies) for AST audit")
    ap.add_argument("--bib", help="Optional .bib file for citation_audit.py")
    ap.add_argument("--strict", action="store_true", help="Treat MEDIUM AST findings as blocking too")
    ap.add_argument("--reviewer-provider", choices=["none", "dry-run", "codex-cli", "claude-cli", "openai", "anthropic"],
                    default="none", help="Optional Layer-2 path-only cross-model reviewer (default: none = Layer-1 only)")
    ap.add_argument("--reviewer-model", default="default", help="Model name for Layer-2 reviewer")
    ap.add_argument("--out-json", help="Optional path to save structured gate report JSON")
    a = ap.parse_args()

    ws = Path(a.workspace).resolve()
    report_p = Path(a.report) if Path(a.report).is_absolute() else (ws / a.report)
    logs_p = [str(Path(x) if Path(x).is_absolute() else (ws / x)) for x in a.logs]
    scripts_p = [str(Path(x) if Path(x).is_absolute() else (ws / x)) for x in a.scripts]

    result = {
        "workspace": str(ws),
        "report": str(report_p),
        "blocked": False,
        "block_reasons": [],
        "checks": {},
    }

    # 1. Numerical provenance (trace_numbers.py)
    cmd_tr = [sys.executable, str(RL_SCRIPTS / "trace_numbers.py"), str(report_p), "--logs", *logs_p, "--json"]
    if scripts_p:
        cmd_tr.extend(["--scripts", *scripts_p])
    rc, out, err = run_cmd(cmd_tr)
    try:
        tr_data = json.loads(out)
    except json.JSONDecodeError:
        tr_data = {"raw_stdout": out, "raw_stderr": err, "returncode": rc}
    result["checks"]["trace_numbers"] = {"returncode": rc, "summary": tr_data}
    if rc != 0:
        result["blocked"] = True
        result["block_reasons"].append(
            f"trace_numbers failed (untraced={len(tr_data.get('untraced', []))}, "
            f"sign={len(tr_data.get('sign_mismatches', []))}, "
            f"wrong_log={len(tr_data.get('wrong_log', []))})"
            if isinstance(tr_data, dict) else f"trace_numbers exited {rc}"
        )

    # 2. Python AST code integrity (audit_code.py)
    if scripts_p:
        cmd_ast = [sys.executable, str(RL_SCRIPTS / "audit_code.py"), "--report", str(report_p), "--json", "--strict"]
        for sp in scripts_p:
            cmd_ast.extend(["--scripts", sp])
        rc, out, err = run_cmd(cmd_ast)
        try:
            ast_data = json.loads(out)
        except json.JSONDecodeError:
            ast_data = {"raw_stdout": out, "raw_stderr": err, "returncode": rc}
        result["checks"]["audit_code"] = {"returncode": rc, "summary": ast_data}
        mediums = [f.get("code") for f in ast_data.get("findings", []) if f.get("severity") == "MEDIUM"] if isinstance(ast_data, dict) else []
        if rc != 0 or (a.strict and mediums):
            result["blocked"] = True
            highs = [f.get("code") for f in ast_data.get("findings", []) if f.get("severity") == "HIGH"] if isinstance(ast_data, dict) else []
            result["block_reasons"].append(f"audit_code failed (HIGH={len(highs)}: {sorted(set(highs))}, MEDIUM={len(mediums)})")

    # 3. Optional citation audit (citation_audit.py)
    if a.bib:
        bib_p = Path(a.bib) if Path(a.bib).is_absolute() else (ws / a.bib)
        cmd_cit = [sys.executable, str(RL_SCRIPTS / "citation_audit.py"), str(report_p), "--bib", str(bib_p), "--json"]
        rc, out, err = run_cmd(cmd_cit)
        try:
            cit_data = json.loads(out)
        except json.JSONDecodeError:
            cit_data = {"raw_stdout": out, "raw_stderr": err, "returncode": rc}
        result["checks"]["citation_audit"] = {"returncode": rc, "summary": cit_data}
        if rc != 0:
            result["blocked"] = True
            result["block_reasons"].append(f"citation_audit failed (rc={rc})")

    # 4. Optional claim ledger status check (claims.py)
    claims_file = ws / "claims.json"
    if claims_file.is_file():
        rc, out, err = run_cmd([sys.executable, str(RL_SCRIPTS / "claims.py"), "-w", str(ws), "check"])
        result["checks"]["claims_ledger"] = {"returncode": rc, "stdout": out.strip(), "stderr": err.strip()}
        if rc != 0:
            result["blocked"] = True
            result["block_reasons"].append(f"claims ledger check failed (rc={rc})")

    # 5. Optional Layer-2 Path-Isolated Cross-Model Audit (run_audit.py)
    if a.reviewer_provider != "none":
        audit_out = ws / "audits/verifiable-gate-review.md"
        audit_out.parent.mkdir(parents=True, exist_ok=True)
        cmd_xmr = [
            sys.executable, str(RL_SCRIPTS / "run_audit.py"),
            "--workspace", str(ws),
            "--report", str(report_p),
            "--provider", a.reviewer_provider,
            "--model", a.reviewer_model,
            "--out", str(audit_out),
        ]
        for lp in logs_p:
            cmd_xmr.extend(["--logs", lp])
        for sp in scripts_p:
            cmd_xmr.extend(["--scripts", sp])
        rc, out, err = run_cmd(cmd_xmr)
        review_verdict = None
        if audit_out.is_file():
            import re as _re
            txt = audit_out.read_text(encoding="utf-8", errors="ignore")
            m = _re.search(r'"overall_decision"\s*:\s*"([A-Z_]+)"', txt)
            if m:
                review_verdict = m.group(1)
        result["checks"]["cross_model_audit"] = {
            "returncode": rc,
            "review_path": str(audit_out),
            "overall_decision": review_verdict,
            "stdout": out[-1000:],
        }
        if rc != 0 or (review_verdict and review_verdict.startswith("BLOCK_")):
            result["blocked"] = True
            result["block_reasons"].append(
                f"path-isolated cross-model audit blocked (decision={review_verdict}, rc={rc}, see {audit_out})"
            )

    if a.out_json:
        out_fp = Path(a.out_json) if Path(a.out_json).is_absolute() else (ws / a.out_json)
        out_fp.parent.mkdir(parents=True, exist_ok=True)
        out_fp.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    status = "BLOCKED" if result["blocked"] else "PASSED"
    print(f"VERIFIABLE_GATE: {status}")
    for r in result["block_reasons"]:
        print(f"  - {r}")
    sys.exit(2 if result["blocked"] else 0)


if __name__ == "__main__":
    main()
