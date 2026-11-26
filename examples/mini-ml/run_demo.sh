#!/usr/bin/env bash
# End-to-end 10-second demonstration of the 5-step research-loop (0 API spend).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPTS="$ROOT/skills/research-loop/scripts"
WS="${1:-$(mktemp -d)}"
echo "Demo workspace: $WS"
mkdir -p "$WS/out" "$WS/reports" "$WS/audits"

# Step 1: Register falsifiable claim before running
python3 "$SCRIPTS/claims.py" -w "$WS" add C1 \
  --text "L2-regularized logistic regression (valid-selected lr) beats 1-epoch baseline on synthetic test accuracy across 3 seeds" \
  --metric "Test Accuracy" --select-on valid --seeds 3 --baselines "baseline" \
  --kill "baseline matches or beats method on 3-seed test accuracy" \
  --scope "8-D synthetic Gaussian classification, n_test=400"

# Step 2: Run 3 seeds sequentially with resume + live watchdog
for ARM in baseline method ablation_nol2; do
  python3 "$SCRIPTS/run_seeds.py" --name "$ARM" --seeds 0,1,2 --out-dir "$WS/out" \
    --cmd "python3 $ROOT/examples/mini-ml/train_demo.py --arm $ARM --seed {seed}" \
    --complete-marker "SUMMARY_COMPLETE"
done

# Aggregate 3-seed logs into one summary log & attach SHA-256 verified evidence
python3 - "$WS/out" <<'PY'
import glob, re, statistics, sys
out_dir = sys.argv[1]
lines = []
for arm in ("baseline", "method", "ablation_nol2"):
    accs = []
    for p in sorted(glob.glob(f"{out_dir}/{arm}_s*.txt")):
        txt = open(p).read()
        m = re.search(r"split=test\s+n=\d+\s+acc=([0-9.]+)", txt)
        if m:
            accs.append(float(m.group(1)))
    mean = statistics.mean(accs)
    sd = statistics.stdev(accs) if len(accs) > 1 else 0.0
    lines.append(f"{arm:14s} | seeds={len(accs)} | test_acc={mean:.4f}±{sd:.4f} | per_seed={accs}")
lines.append("SUMMARY_COMPLETE")
open(f"{out_dir}/aggregate.txt", "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
PY

python3 "$SCRIPTS/claims.py" -w "$WS" evidence C1 --log "$WS/out/aggregate.txt" \
  --dataset synth --seeds 3 --selected-on valid --n 400 --changes 2 --ablated 1 --has-ci --complete-marker "SUMMARY_COMPLETE"
python3 "$SCRIPTS/claims.py" -w "$WS" evidence C1 --role ablation --log "$WS/out/ablation_nol2_s0.txt" \
  --dataset synth --seeds 3 --selected-on valid --n 400 --changes 2 --ablated 1 --complete-marker "SUMMARY_COMPLETE"
python3 "$SCRIPTS/claims.py" -w "$WS" evidence C1 --arm baseline --log "$WS/out/aggregate.txt" \
  --seeds 3 --selected-on valid --n 400 --complete-marker "SUMMARY_COMPLETE"

# Step 3: Draft report & run deterministic verification (trace + AST code audit + gates)
python3 - "$WS" <<'PY'
import re, sys
ws = sys.argv[1]
agg = open(f"{ws}/out/aggregate.txt").read()
rows = []
for arm in ("baseline", "method", "ablation_nol2"):
    m = re.search(rf"^{arm}\s+\|\s+seeds=3\s+\|\s+test_acc=([0-9.]+±[0-9.]+)", agg, re.M)
    rows.append(f"| `{arm}` | 3 | `{m.group(1)}` | `aggregate.txt` |")
md = "# Mini-ML Demo Report\n\n| Arm | Seeds | Test Acc | Log |\n|---|---:|---|---|\n" + "\n".join(rows) + "\n"
open(f"{ws}/reports/demo.md", "w").write(md)
PY

python3 "$SCRIPTS/trace_numbers.py" "$WS/reports/demo.md" --logs "$WS/out" --scripts "$ROOT/examples/mini-ml"
python3 "$SCRIPTS/audit_code.py" --scripts "$ROOT/examples/mini-ml" --report "$WS/reports/demo.md" --strict
python3 "$SCRIPTS/claims.py" -w "$WS" check

# Step 4: Dry-run independent audit + render verifiable HTML board
python3 "$SCRIPTS/run_audit.py" -w "$WS" --report "$WS/reports/demo.md" --logs "$WS/out" \
  --scripts "$ROOT/examples/mini-ml" --mode kill-adjudicate --provider dry-run --model dry-run
python3 "$SCRIPTS/render_board.py" -w "$WS"
echo "Demo passed! Board: $WS/board.html"
