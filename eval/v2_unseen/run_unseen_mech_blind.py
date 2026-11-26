#!/usr/bin/env python3
"""Strictly Unseen 21-Scenario SciIntegrity-Bench Blind Test of Frozen v2 Mechanical Gates.

Guarantees:
  1. Verifies exact SHA-256 lock of frozen trace_numbers.py and audit_code.py BEFORE running.
  2. Runs ONLY the 21 SciIntegrity-Bench scenarios NEVER touched during v1 or gate development.
  3. Runs bare claude-haiku executor with the official SciIntegrity unified prompt on isolated
     copies (private ground-truth stripped).
  4. Evaluates every produced workspace with the frozen v2 mechanical gates (ZERO overrides)
     and records full raw findings verbatim to JSONL for line-by-line TP vs FP auditing.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNSEEN_DIR = Path(__file__).resolve().parent
RL_SCRIPTS = ROOT / "skills/research-loop/scripts"
sys.path.insert(0, str(ROOT / "eval"))
import run_benchmark as rb  # noqa: E402

FROZEN_SHA256 = {
    "trace_numbers.py": "42c39cf4a4adeee1",
    "audit_code.py": "72dac256a9caf775",
}

PREVIOUSLY_TOUCHED = {
    "01b_ComputationalLinguistics_MorphologicalSegmentationSuite",
    "01c_BiomedicalImaging_CellBenchmarkPicker",
    "02b_FinancialML_CreditDefaultSPR",
    "03a_RecommendationSystem_RecSysV2LaunchEvaluation",
    "04a_RareEvent_ClassificationKPI",
    "05a_SocialScience_InterviewThematicAnalysis",
    "06a_RetailAnalytics_AdSpendStoreSales",
    "07c_ClinicalOps_ColdChainShipmentProtocol",
    "08a_StructuralHealth_SensorVibrationPanel",
    "09a_NuclearScience_Iodine131DecayAnalysis",
    "10a_Archaeology_RadiocarbonSiteChronology",
    "11a_DataScience_TelemetryExportMergeReport",
}


def verify_frozen_gates(allow_updated: bool = False) -> dict:
    hashes = {}
    for name, expected_prefix in FROZEN_SHA256.items():
        p = RL_SCRIPTS / name
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        if not h.startswith(expected_prefix):
            if not allow_updated:
                raise RuntimeError(
                    f"FROZEN GATE HASH MISMATCH for {name}: got {h[:16]}, expected {expected_prefix}! "
                    "Refusing to run unseen blind test on modified gate "
                    "(pass --allow-updated-gate to evaluate a post-v2 gate version explicitly)."
                )
            print(
                f"[WARN] Running unseen test with UPDATED gate {name} sha256={h[:16]} "
                f"(v2 paper frozen sha256 was {expected_prefix})",
                file=sys.stderr,
            )
        hashes[name] = h
    return hashes


def run_frozen_gates(ws: Path, include_data: bool = False) -> dict:
    rep = ws / "report/report.md"
    if not rep.is_file():
        return {"report_exists": False, "mech_blocked": False, "trace": {}, "audit": {}}

    # Collect all log dirs (out/ and outputs/)
    log_dirs = [d for d in (ws / "out", ws / "outputs") if d.is_dir() and any(d.rglob("*"))]
    trace_data = {"traced": 0, "untraced": [], "sign_mismatches": [], "wrong_logs": [], "unpaired_pairs": []}
    trace_rc = 0
    if log_dirs:
        cmd = [sys.executable, str(RL_SCRIPTS / "trace_numbers.py"), str(rep), "--json"]
        for ld in log_dirs:
            cmd.extend(["--logs", str(ld)])
        if include_data and (ws / "data").is_dir():
            cmd.extend(["--data", str(ws / "data")])
        p = subprocess.run(cmd, capture_output=True, text=True)
        trace_rc = p.returncode
        if p.stdout.strip().startswith("{"):
            trace_data = json.loads(p.stdout)

    code_dir = ws / "code"
    audit_data = {"counts": {"HIGH": 0, "MEDIUM": 0, "INFO": 0}, "findings": []}
    audit_rc = 0
    if code_dir.is_dir() and any(code_dir.rglob("*.py")):
        p2 = subprocess.run(
            [sys.executable, str(RL_SCRIPTS / "audit_code.py"), "--scripts", str(code_dir), "--report", str(rep), "--json", "--strict"],
            capture_output=True, text=True,
        )
        audit_rc = p2.returncode
        if p2.stdout.strip().startswith("{"):
            audit_data = json.loads(p2.stdout)

    trace_blk = (
        len(trace_data.get("untraced", [])) > 0
        or len(trace_data.get("sign_mismatches", [])) > 0
        or len(trace_data.get("wrong_logs", [])) > 0
        or len(trace_data.get("unpaired_pairs", [])) > 0
    )
    ast_blk = int(audit_data.get("counts", {}).get("HIGH", 0)) > 0
    return {
        "report_exists": True,
        "mech_blocked": bool(trace_blk or ast_blk),
        "trace_blocked": bool(trace_blk),
        "ast_blocked": bool(ast_blk),
        "trace_rc": trace_rc,
        "audit_rc": audit_rc,
        "traced": int(trace_data.get("traced", 0)),
        "untraced": trace_data.get("untraced", []),
        "sign_mismatches": trace_data.get("sign_mismatches", []),
        "wrong_logs": trace_data.get("wrong_logs", []),
        "unpaired_pairs": trace_data.get("unpaired_pairs", []),
        "ast_high": int(audit_data.get("counts", {}).get("HIGH", 0)),
        "ast_medium": int(audit_data.get("counts", {}).get("MEDIUM", 0)),
        "ast_findings": [f for f in audit_data.get("findings", []) if f.get("severity") in ("HIGH", "MEDIUM")],
    }


def run_haiku_executor(prompt: str, ws: Path, timeout: int, max_usd: float) -> tuple[float, str | None]:
    cmd = [
        "claude", "-p", "--output-format", "json", "--no-session-persistence",
        "--permission-mode", "bypassPermissions",
        "--max-budget-usd", f"{max_usd:.2f}",
        "--add-dir", str(ws),
        "--model", "haiku",
    ]
    p = subprocess.run(cmd, cwd=str(ws), input=prompt, capture_output=True, text=True, timeout=timeout)
    cost = 0.0
    if p.stdout.strip().startswith("{"):
        try:
            body = json.loads(p.stdout)
            cost = float(body.get("total_cost_usd", 0.0))
        except Exception:
            pass
    if p.returncode != 0 and not (ws / "report/report.md").is_file():
        return cost, f"claude-haiku rc={p.returncode}: {(p.stderr or p.stdout)[:300]}"
    return cost, None


def main():
    ap = argparse.ArgumentParser(description="Run 21 strictly unseen SciIntegrity scenarios under frozen v2 gates.")
    ap.add_argument("--bench-root", default="/home/shawnyang/Documents/auto-research/external/Sci-Integrity-Bench")
    ap.add_argument("--out-dir", default=str(UNSEEN_DIR))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--max-usd-per-task", type=float, default=0.50)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--allow-updated-gate", action="store_true",
                    help="Allow running on post-v2 updated gate scripts (passes --data when present)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    gate_hashes = verify_frozen_gates(allow_updated=args.allow_updated_gate)
    out_dir = Path(args.out_dir).resolve()
    ws_root = out_dir / "workspaces"
    ws_root.mkdir(parents=True, exist_ok=True)
    out_jsonl = out_dir / "results_unseen_21.jsonl"

    all_scens = rb.list_sciintegrity_scenarios(args.bench_root)
    unseen = [s for s in all_scens if s["id"] not in PREVIOUSLY_TOUCHED]

    completed = set()
    if args.resume and out_jsonl.is_file():
        for line in out_jsonl.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if not r.get("exec_error") and r.get("gates", {}).get("report_exists"):
                    completed.add(r["scenario_id"])

    todo = [s for s in unseen if s["id"] not in completed]
    if args.dry_run:
        print(
            f"UNSEEN_BLIND DRY_RUN OK | total_unseen={len(unseen)} | resumed={len(completed)} | todo={len(todo)} | "
            f"trace_sha={gate_hashes['trace_numbers.py'][:16]} | audit_sha={gate_hashes['audit_code.py'][:16]}"
        )
        sys.exit(0)

    spec_bare = rb.conditions.CONDITIONS["B0_bare"]
    lock = threading.Lock()
    done_cnt = [0]
    total_cost = [0.0]

    def run_one(scen):
        sid = scen["id"]
        ws = ws_root / sid
        rb.prepare_isolated_workspace(scen, ws)
        prompt = rb.build_executor_prompt(scen, spec_bare, str(ws), use_pressure=True)
        t0 = time.time()
        try:
            cost, err = run_haiku_executor(prompt, ws, args.timeout, args.max_usd_per_task)
        except Exception as e:
            cost, err = 0.0, str(e)[:300]
        elapsed = round(time.time() - t0, 2)
        gates = run_frozen_gates(ws, include_data=args.allow_updated_gate)

        rec = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "scenario_id": sid,
            "trap": scen["trap"],
            "executor": "claude-haiku",
            "frozen_gate_sha256": {k: v[:16] for k, v in gate_hashes.items()},
            "elapsed_s": elapsed,
            "cost_usd": round(cost, 6),
            "exec_error": err,
            "gates": gates,
        }
        with lock:
            with out_jsonl.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
            done_cnt[0] += 1
            total_cost[0] += cost
            g = gates
            print(
                f"[{done_cnt[0]}/{len(todo)}] {sid[:28]:28s} | blk={str(g.get('mech_blocked')):5s} | "
                f"tr={g.get('traced',0):2d} u={len(g.get('untraced',[]))} s={len(g.get('sign_mismatches',[]))} "
                f"wl={len(g.get('wrong_logs',[]))} up={len(g.get('unpaired_pairs',[]))} astH={g.get('ast_high',0)} | "
                f"${cost:.4f} {elapsed}s" + (f" ERR={err[:60]}" if err else ""),
                flush=True,
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futs = [pool.submit(run_one, s) for s in todo]
        for fut in concurrent.futures.as_completed(futs):
            fut.result()

    print(f"UNSEEN_21 COMPLETE: ran={done_cnt[0]} total_cost=${total_cost[0]:.4f} out={out_jsonl}")


if __name__ == "__main__":
    main()
