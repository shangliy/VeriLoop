#!/usr/bin/env python3
"""Live end-to-end VeriLoop showcase:
  1. Generates a clean local benchmark dataset (train/val/test CSV, 0 leakage) + refs.bib
  2. Runs a real autonomous executor (claude-cli haiku) to code, train, ablate, and draft report.md
  3. Runs tools/verifiable_gate.py (Layer 1 deterministic AST/provenance/citation + Layer 2 path-only codex-cli XMR)
  4. If Round 1 blocks, runs 1 targeted closed-loop repair turn + Round-2 verification
  5. Tracks exact USD spend under a strict $1.50 circuit breaker and renders board.html
"""
import argparse
import csv
import json
import math
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RL_SCRIPTS = ROOT / "skills/research-loop/scripts"
GATE = ROOT / "tools/verifiable_gate.py"
sys.path.insert(0, str(RL_SCRIPTS))
import budget  # noqa: E402


def generate_dataset(csv_path: Path, seed: int = 42):
    rng = random.Random(seed)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    # 1200 rows: 700 train, 250 val, 250 test; nonlinear interaction + Gaussian noise
    splits = ["train"] * 700 + ["val"] * 250 + ["test"] * 250
    w_lin = [0.9, -0.7, 0.5, -0.3, 0.15, -0.1, 0.0, 0.0]
    with open(csv_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "split", *[f"f{i}" for i in range(8)], "label"])
        for idx, sp in enumerate(splits):
            x = [rng.gauss(0.0, 1.0) for _ in range(8)]
            logit = sum(a * b for a, b in zip(w_lin, x)) + 0.85 * (x[0] * x[1]) - 0.5 * (x[2] ** 2 - 1.0)
            prob = 1.0 / (1.0 + math.exp(-logit))
            # Flip 8% label noise so Bayes ceiling is realistic (~85-88%)
            y = 1 if rng.random() < prob else 0
            if rng.random() < 0.08:
                y = 1 - y
            w.writerow([idx, sp, *[f"{v:.5f}" for v in x], y])


def run_claude_executor(prompt: str, ws: Path, budget_file: str, budget_limit: float, role: str):
    budget.check_budget(budget_file, 0.08, default_limit=budget_limit)
    cmd = [
        "claude", "-p",
        "--output-format", "json",
        "--no-session-persistence",
        "--permission-mode", "bypassPermissions",
        "--max-budget-usd", "0.50",
        "--add-dir", str(ws),
        "--model", "haiku",
    ]
    t0 = time.monotonic()
    p = subprocess.run(cmd, cwd=str(ws), input=prompt, capture_output=True, text=True, timeout=360)
    dt = time.monotonic() - t0
    if p.returncode != 0:
        raise RuntimeError(f"claude executor failed (rc={p.returncode}): {p.stderr[:400]}")
    data = json.loads(p.stdout)
    u = data.get("usage", {})
    in_t = int(u.get("input_tokens", 0)) + int(u.get("cache_read_input_tokens", 0)) + int(u.get("cache_creation_input_tokens", 0))
    out_t = int(u.get("output_tokens", 0))
    cost = float(data.get("total_cost_usd", 0.0))
    budget.record_call(
        budget_file, "claude-cli", "haiku", role, "live_showcase",
        in_t, out_t, default_limit=budget_limit, actual_cost_usd=cost,
    )
    return data.get("result", ""), cost, dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=str(ROOT / "examples/live-showcase/workspace"))
    ap.add_argument("--budget-limit", type=float, default=1.50)
    ap.add_argument("--reviewer-provider", default="codex-cli")
    ap.add_argument("--reviewer-model", default="default")
    a = ap.parse_args()

    ws = Path(a.workspace).resolve()
    if ws.exists():
        shutil.rmtree(ws)
    for sub in ("data", "code", "out", "report", "audits"):
        (ws / sub).mkdir(parents=True, exist_ok=True)

    generate_dataset(ws / "data/dataset.csv")
    (ws / "refs.bib").write_text(
        "@article{yang2026aris,\n"
        "  title={{ARIS}: Autonomous Research via Adversarial Multi-Agent Collaboration},\n"
        "  author={Yang, Ruofeng and Li, Yongcan and Li, Shuai},\n"
        "  journal={arXiv preprint arXiv:2605.03042},\n"
        "  year={2026}\n"
        "}\n"
    )
    budget_file = str(ws / "budget_ledger.json")

    # Pre-register claim C1
    subprocess.run([
        sys.executable, str(RL_SCRIPTS / "claims.py"), "-w", str(ws), "add", "C1",
        "--text", "Interaction-aware L2 logistic regression beats linear baseline on 3-seed test accuracy on dataset.csv",
        "--metric", "Test Accuracy", "--select-on", "valid", "--seeds", "3",
        "--baselines", "linear_baseline",
        "--kill", "linear_baseline matches or exceeds interaction model on 3-seed test accuracy",
        "--scope", "Synthetic 8-feature nonlinear classification dataset (n_test=250)",
    ], check=True)

    print(f"=== Live VeriLoop Showcase Workspace: {ws} (Budget Cap: ${a.budget_limit:.2f}) ===")
    exec_prompt = f"""You are an autonomous ML researcher working inside `{ws}`.
Task:
1. Read `data/dataset.csv` (`id,split,f0..f7,label`; splits are `train`, `val`, `test`). Do NOT modify `data/`.
2. Write a clean, fast CPU-only Python script `code/run_experiment.py` (stdlib + numpy/scipy only; NO hardcoded metric prints, NO test-set tuning, NO mock data) comparing 3 arms across 3 random seeds (0, 1, 2):
   - `linear_baseline`: L2-regularized logistic regression on raw `f0..f7`
   - `interaction_method`: L2-regularized logistic regression adding pairwise/quadratic features (`f0*f1`, `f2^2`, etc.), tuning L2 regularization ONLY on `val`
   - `ablation_no_l2`: same interaction features without L2 regularization
3. Execute `python3 code/run_experiment.py > out/results.txt` and print exact 3-seed mean±std, paired 95% bootstrap CI of (method - baseline) on `test`, per-seed scores, and end with `SUMMARY_COMPLETE`.
4. Write a concise, strictly honest report in `report/report.md` citing `\\cite{{yang2026aris}}` and referencing `out/results.txt`. Every decimal (>=3 places) in `report/report.md` MUST appear verbatim with exact sign in `out/results.txt`.
"""
    print("\n>>> [Round 1] Running autonomous executor (claude-haiku)...")
    _, c1, dt1 = run_claude_executor(exec_prompt, ws, budget_file, a.budget_limit, "executor_r1")
    print(f"    Executor R1 done in {dt1:.1f}s (${c1:.4f})")

    # Register log evidence for C1 if out/results.txt exists
    res_log = ws / "out/results.txt"
    if res_log.is_file():
        for extra in (
            ["--dataset", "synth", "--seeds", "3", "--selected-on", "valid", "--n", "250", "--changes", "2", "--ablated", "1", "--has-ci", "--complete-marker", "SUMMARY_COMPLETE"],
            ["--role", "ablation", "--dataset", "synth", "--seeds", "3", "--selected-on", "valid", "--n", "250", "--changes", "2", "--ablated", "1", "--complete-marker", "SUMMARY_COMPLETE"],
            ["--arm", "linear_baseline", "--seeds", "3", "--selected-on", "valid", "--n", "250", "--complete-marker", "SUMMARY_COMPLETE"],
        ):
            subprocess.run([sys.executable, str(RL_SCRIPTS / "claims.py"), "-w", str(ws), "evidence", "C1", "--log", str(res_log), *extra], check=False)

    print("\n>>> [Round 1] Running VeriLoop Hard Gate (Layer 1 deterministic + Layer 2 path-only codex-cli)...")
    t0 = time.monotonic()
    p1 = subprocess.run([
        sys.executable, str(GATE),
        "-w", str(ws),
        "--report", "report/report.md",
        "--logs", "out",
        "--scripts", "code",
        "--bib", "refs.bib",
        "--reviewer-provider", a.reviewer_provider,
        "--reviewer-model", a.reviewer_model,
        "--budget-file", budget_file,
        "--budget-limit", str(a.budget_limit),
        "--out-json", "audits/r1_gate.json",
    ], capture_output=True, text=True)
    print(p1.stdout.strip())
    if p1.stderr.strip():
        print(p1.stderr.strip())
    print(f"    Gate R1 finished in {time.monotonic() - t0:.1f}s (rc={p1.returncode})")

    if p1.returncode != 0:
        shutil.copyfile(ws / "report/report.md", ws / "report/report_r1_blocked.md")
        r1_json = (ws / "audits/r1_gate.json").read_text() if (ws / "audits/r1_gate.json").exists() else ""
        r1_rev = (ws / "audits/verifiable-gate-review.md").read_text() if (ws / "audits/verifiable-gate-review.md").exists() else ""
        if (ws / "audits/verifiable-gate-review.md").exists():
            shutil.copyfile(ws / "audits/verifiable-gate-review.md", ws / "audits/r1_review.md")

        print("\n>>> [Round 2] Round 1 BLOCKED — running 1 targeted closed-loop repair turn (claude-haiku)...")
        repair_prompt = f"""Your Round-1 submission in `{ws}` was HARD-BLOCKED by VeriLoop.
Fix EVERY mechanical and reviewer issue below by editing `code/` (re-running `out/results.txt` if needed) and `report/report.md`.
Do NOT fabricate numbers; every decimal (>=3 places) in `report/report.md` must match `out/results.txt` verbatim with exact sign and paired CI/± lines.

=== Mechanical Gate Summary ===
{r1_json[:3000]}

=== Independent Path-Only Reviewer Audit ===
{r1_rev[:5000]}
"""
        _, c2, dt2 = run_claude_executor(repair_prompt, ws, budget_file, a.budget_limit, "executor_r2_repair")
        print(f"    Executor R2 repair done in {dt2:.1f}s (${c2:.4f})")

        # Re-anchor evidence hash in case out/results.txt was updated during repair
        if res_log.is_file():
            subprocess.run([
                sys.executable, str(RL_SCRIPTS / "claims.py"), "-w", str(ws), "evidence", "C1",
                "--log", str(res_log), "--dataset", "synth", "--seeds", "3",
                "--selected-on", "valid", "--n", "250", "--changes", "2", "--ablated", "1",
                "--has-ci", "--complete-marker", "SUMMARY_COMPLETE",
            ], check=False)

        print("\n>>> [Round 2] Re-running VeriLoop Hard Gate (Layer 1 + Layer 2 path-only codex-cli)...")
        t1 = time.monotonic()
        p2 = subprocess.run([
            sys.executable, str(GATE),
            "-w", str(ws),
            "--report", "report/report.md",
            "--logs", "out",
            "--scripts", "code",
            "--bib", "refs.bib",
            "--reviewer-provider", a.reviewer_provider,
            "--reviewer-model", a.reviewer_model,
            "--budget-file", budget_file,
            "--budget-limit", str(a.budget_limit),
            "--out-json", "audits/r2_gate.json",
        ], capture_output=True, text=True)
        print(p2.stdout.strip())
        if p2.stderr.strip():
            print(p2.stderr.strip())
        print(f"    Gate R2 finished in {time.monotonic() - t1:.1f}s (rc={p2.returncode})")

    subprocess.run([sys.executable, str(RL_SCRIPTS / "render_board.py"), "-w", str(ws)], check=False)
    bdb = budget.load_ledger(budget_file, default_limit=a.budget_limit)
    print(f"\n=== LIVE SHOWCASE COMPLETE | Total API Spend: ${bdb['spent_usd']:.4f} / ${bdb['limit_usd']:.2f} ({len(bdb['calls'])} calls) ===")
    print(f"Board: {ws / 'board.html'}")


if __name__ == "__main__":
    main()
