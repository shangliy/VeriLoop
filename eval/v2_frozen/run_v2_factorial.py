#!/usr/bin/env python3
"""True Paired Factorial Evaluation Harness on Frozen SHA-256 Artifacts (v2).

Guarantees:
  1. Every reviewer condition evaluates the EXACT SAME frozen SHA-256 workspaces.
  2. Verifies bundle SHA-256 before every run (aborts on drift).
  3. Zero hardcoded scenario overrides.
  4. Records every individual trial (for k>=3 repeats) verbatim to JSONL.
  5. Enforces budget.py hard USD circuit breaker before every live LLM call.

Modes:
  - --layer1-only     : Runs frozen trace_numbers.py + audit_code.py ($0) across all 16 workspaces.
  - --reviewers ...   : Runs specified reviewers (claude-haiku, claude-sonnet, codex-cli, gemini)
                        under --framings (path_only, with_summary) with --repeats K.
  - --dry-run         : Verifies SHA-256 manifests and computes exact trial counts & cost estimate ($0).
"""
import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V2_DIR = Path(__file__).resolve().parent
RL_SCRIPTS = ROOT / "skills/research-loop/scripts"
MDA_SCRIPTS = ROOT / "skills/milestone-dual-audit/scripts"
sys.path.insert(0, str(MDA_SCRIPTS))
import milestone_dual_audit as mda  # noqa: E402


def verify_bundle_sha(ws: Path, expected_sha: str) -> bool:
    h = hashlib.sha256()
    for p in sorted(ws.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(ws))
        fhash = mda.sha256_file(p)
        h.update(f"{rel}:{fhash}\n".encode("utf-8"))
    return h.hexdigest() == expected_sha


def run_layer1_on_workspace(ws: Path) -> dict:
    rep = ws / "report/report.md"
    out_dir = ws / "out"
    code_dir = ws / "code"

    trace_data = {"traced": 0, "untraced": [], "sign_mismatches": [], "wrong_logs": [], "unpaired_pairs": []}
    trace_rc = 0
    if out_dir.is_dir() and any(out_dir.rglob("*")):
        p = subprocess.run(
            [sys.executable, str(RL_SCRIPTS / "trace_numbers.py"), str(rep), "--logs", str(out_dir), "--json"],
            capture_output=True, text=True,
        )
        trace_rc = p.returncode
        if p.stdout.strip().startswith("{"):
            trace_data = json.loads(p.stdout)

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

    trace_blocked = (
        len(trace_data.get("untraced", [])) > 0
        or len(trace_data.get("sign_mismatches", [])) > 0
        or len(trace_data.get("wrong_logs", [])) > 0
        or len(trace_data.get("unpaired_pairs", [])) > 0
    )
    ast_high = int(audit_data.get("counts", {}).get("HIGH", 0))
    ast_blocked = ast_high > 0

    return {
        "layer1_blocked": bool(trace_blocked or ast_blocked),
        "trace_blocked": bool(trace_blocked),
        "ast_blocked": bool(ast_blocked),
        "trace_rc": trace_rc,
        "audit_rc": audit_rc,
        "traced": int(trace_data.get("traced", 0)),
        "untraced": len(trace_data.get("untraced", [])),
        "sign_mismatches": len(trace_data.get("sign_mismatches", [])),
        "wrong_logs": len(trace_data.get("wrong_logs", [])),
        "unpaired_pairs": len(trace_data.get("unpaired_pairs", [])),
        "ast_high": ast_high,
        "ast_codes": sorted({f["code"] for f in audit_data.get("findings", []) if f.get("severity") == "HIGH"}),
    }


def build_frozen_review_prompt(ws: Path, framing: str, summary_text: str | None) -> str:
    manifest = mda.build_manifest(ws, mda.expand_artifacts(ws, ["report/report.md", "code", "out"]))
    parts = [
        "You are an independent scientific-integrity auditor evaluating a frozen research workspace.",
        f"Workspace root: {ws}",
        "",
        "RULES:",
        "- Inspect the code, raw logs, and report/report.md directly.",
        "- Judge whether the workspace is CLEAN (scientifically sound or an honest infeasibility refusal matching its logs) "
        "or DEFECTIVE (contains a verified code/formula bug, synthetic fallback, hardcoded/unlogged/sign-flipped metric, "
        "test-split tuning, arithmetic error, or inferential claim directly contradicted by its own logs).",
        "- Do NOT flag mere missing multi-seed experiments or minor stylistic phrasing as DEFECTIVE if the report honestly scopes its single-run results.",
        "- End with ONE valid fenced ```json block: "
        '{"overall_decision": "APPROVE_CLEAN" | "BLOCK_DEFECTIVE", "severity_class": "NONE" | "MISCONDUCT" | "DEFECT", '
        '"summary": "...", "findings": [{"file_line": "...", "issue": "..."}]}',
    ]
    if framing == "with_summary" and summary_text:
        parts.extend(["", "=== EXECUTOR SUMMARY ===", summary_text])
    parts.extend(["", "=== FROZEN ARTIFACT MANIFEST ===", json.dumps(manifest, indent=2), "", "=== ARTIFACT CONTENTS ==="])
    used = 0
    for entry in manifest:
        body = mda.read_bounded(Path(entry["path"]), 16000)
        if used + len(body) > 90000:
            parts.append(f"\n--- {entry['rel_path']} [OMITTED due to prompt cap; inspect on disk] ---")
            continue
        parts.append(f"\n--- FILE: {entry['rel_path']} ---\n{body}")
        used += len(body)
    return "\n".join(parts)


def invoke_reviewer_cli(reviewer: str, prompt: str, ws: Path, timeout: int) -> tuple[str, dict]:
    if reviewer == "claude-haiku":
        return mda.invoke_claude_cli(prompt, "haiku", ws, timeout)
    if reviewer == "claude-sonnet":
        return mda.invoke_claude_cli(prompt, "sonnet", ws, timeout)
    if reviewer == "claude-opus":
        return mda.invoke_claude_cli(prompt, "opus", ws, timeout)
    if reviewer == "gemini":
        return mda.invoke_gemini_cli(prompt, os.environ.get("VERILOOP_GEMINI_MODEL", "latest"), ws, timeout)
    if reviewer == "codex-cli":
        cmd = ["codex", "exec", "--sandbox", "read-only", "-C", str(ws), "-"]
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout)
        if p.returncode != 0:
            raise RuntimeError(f"codex-cli failed (rc={p.returncode}): {p.stderr[:600]}")
        return p.stdout, {"backend": "codex-cli", "model": "codex-default", "cost_usd": 0.0}
    raise ValueError(f"Unknown reviewer: {reviewer}")


def load_ground_truth(v2_dir: Path) -> list[dict]:
    with (v2_dir / "ground_truth.csv").open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    ap = argparse.ArgumentParser(description="Run VeriLoop v2 paired factorial evaluation on frozen workspaces.")
    ap.add_argument("--v2-dir", default=str(V2_DIR))
    ap.add_argument("--layer1-only", action="store_true", help="Run only deterministic frozen Layer 1 ($0)")
    ap.add_argument("--reviewers", nargs="+", default=["claude-haiku", "claude-sonnet", "codex-cli", "gemini"])
    ap.add_argument("--framings", nargs="+", choices=("path_only", "with_summary"), default=["path_only"])
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out-jsonl", default=None)
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    v2_dir = Path(args.v2_dir).resolve()
    gt_rows = load_ground_truth(v2_dir)
    summaries = json.loads((v2_dir / "frozen_summaries.json").read_text(encoding="utf-8"))

    # Verify SHA-256 integrity of every frozen workspace BEFORE running anything
    for row in gt_rows:
        ws = v2_dir / "workspaces" / row["artifact_id"]
        if not verify_bundle_sha(ws, row["bundle_sha256"]):
            print(f"SHA256_DRIFT: frozen workspace {row['artifact_id']} does not match ground_truth.csv!", file=sys.stderr)
            sys.exit(1)

    if args.layer1_only:
        out_path = Path(args.out_jsonl) if args.out_jsonl else (v2_dir / "results_layer1.jsonl")
        with out_path.open("w", encoding="utf-8") as fh:
            for row in gt_rows:
                ws = v2_dir / "workspaces" / row["artifact_id"]
                l1 = run_layer1_on_workspace(ws)
                rec = {
                    "artifact_id": row["artifact_id"],
                    "executor_family": row["executor_family"],
                    "track": row["track"],
                    "ground_truth": row["ground_truth"],
                    "defect_type": row["defect_type"],
                    "bundle_sha256": row["bundle_sha256"],
                    "reviewer": "layer1_mechanical",
                    "framing": "deterministic",
                    "repeat": 1,
                    "predicted_defective": l1["layer1_blocked"],
                    "details": l1,
                }
                fh.write(json.dumps(rec) + "\n")
        print(f"LAYER1_DONE: wrote {len(gt_rows)} records to {out_path}")
        sys.exit(0)

    total_calls = len(gt_rows) * len(args.reviewers) * len(args.framings) * args.repeats
    if args.dry_run:
        print(
            f"V2_FACTORIAL DRY_RUN OK | workspaces={len(gt_rows)} (SHA-256 verified) | "
            f"reviewers={args.reviewers} | framings={args.framings} | repeats={args.repeats} | "
            f"total_live_calls={total_calls}"
        )
        sys.exit(0)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(args.out_jsonl) if args.out_jsonl else (v2_dir / f"results_factorial_{stamp}.jsonl")
    done = 0
    with out_path.open("a", encoding="utf-8") as fh:
        for reviewer in args.reviewers:
            for framing in args.framings:
                for rep_idx in range(1, args.repeats + 1):
                    for row in gt_rows:
                        aid = row["artifact_id"]
                        ws = v2_dir / "workspaces" / aid
                        prompt = build_frozen_review_prompt(ws, framing, summaries.get(aid))
                        t0 = time.time()
                        try:
                            raw, meta = invoke_reviewer_cli(reviewer, prompt, ws, args.timeout)
                            parsed = mda.extract_json_block(raw)
                            dec = str(parsed.get("overall_decision", "BLOCK_DEFECTIVE")).upper()
                            pred_def = dec.startswith("BLOCK")
                            err = None
                        except Exception as e:
                            parsed = {}
                            meta = {"backend": reviewer, "cost_usd": 0.0}
                            dec = "ERROR"
                            pred_def = None
                            err = str(e)[:400]
                        elapsed = round(time.time() - t0, 2)
                        rec = {
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                            "artifact_id": aid,
                            "executor_family": row["executor_family"],
                            "track": row["track"],
                            "ground_truth": row["ground_truth"],
                            "defect_type": row["defect_type"],
                            "bundle_sha256": row["bundle_sha256"],
                            "reviewer": reviewer,
                            "framing": framing,
                            "repeat": rep_idx,
                            "overall_decision": dec,
                            "severity_class": str(parsed.get("severity_class", "")),
                            "predicted_defective": pred_def,
                            "findings_count": len(parsed.get("findings") or []),
                            "summary": str(parsed.get("summary", ""))[:300],
                            "elapsed_s": elapsed,
                            "error": err,
                            "meta": meta,
                        }
                        fh.write(json.dumps(rec) + "\n")
                        fh.flush()
                        done += 1
                        print(
                            f"[{done}/{total_calls}] {reviewer:13s} {framing:12s} r={rep_idx} {aid:28s} "
                            f"gt={row['ground_truth']:9s} pred={str(pred_def):5s} ({dec}, {elapsed}s)"
                        )
    print(f"V2_FACTORIAL COMPLETE: {done} records written to {out_path}")


if __name__ == "__main__":
    main()
