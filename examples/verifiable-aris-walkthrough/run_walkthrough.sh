#!/usr/bin/env bash
# End-to-end Verifiable-ARIS walkthrough (0 API spend):
#   Phase 1: Pre-register claim C1 + run real 3-seed ML experiment & ablation
#   Phase 2: Round 1 (defective report + hardcoded ref print) -> EviBound passes, Verifiable-ARIS HARD BLOCKS (rc=2)
#   Phase 3: Round 2 (1-round closed-loop repair) -> G1-G7 supported + Verifiable-ARIS PASSES (rc=0) + board.html
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPTS="$ROOT/skills/research-loop/scripts"
GATE="$ROOT/tools/verifiable_gate.py"
WS="${1:-$ROOT/examples/verifiable-aris-walkthrough/demo_output}"

rm -rf "$WS"
mkdir -p "$WS/code" "$WS/out" "$WS/report" "$WS/audits"
echo "=== Workspace: $WS ==="

# ----------------------------------------------------------------------------
# PHASE 1: Pre-register falsifiable claim + run real 3-seed ML experiment
# ----------------------------------------------------------------------------
echo ""
echo ">>> [Phase 1] Pre-registering claim C1 & running 3-seed ML experiment (baseline, method, ablation_nol2)..."
cp "$ROOT/examples/mini-ml/train_demo.py" "$WS/code/train_demo.py"

python3 "$SCRIPTS/claims.py" -w "$WS" add C1 \
  --text "L2-regularized logistic regression (valid-selected lr) beats 1-epoch baseline on 3-seed synthetic test accuracy" \
  --metric "Test Accuracy" --select-on valid --seeds 3 --baselines "baseline" \
  --kill "baseline matches or beats method on 3-seed test accuracy" \
  --scope "8-D synthetic Gaussian classification, n_test=400"

for ARM in baseline method ablation_nol2; do
  python3 "$SCRIPTS/run_seeds.py" --name "$ARM" --seeds 0,1,2 --out-dir "$WS/out" \
    --cmd "python3 $WS/code/train_demo.py --arm $ARM --seed {seed}" \
    --complete-marker "SUMMARY_COMPLETE"
done

python3 - "$WS/out" <<'PY'
import glob, re, statistics, sys
out_dir = sys.argv[1]
vals = {}
lines = []
for arm in ("baseline", "method", "ablation_nol2"):
    accs = []
    for p in sorted(glob.glob(f"{out_dir}/{arm}_s*.txt")):
        m = re.search(r"split=test\s+n=\d+\s+acc=([0-9.]+)", open(p).read())
        if m:
            accs.append(float(m.group(1)))
    mean = statistics.mean(accs)
    sd = statistics.stdev(accs) if len(accs) > 1 else 0.0
    vals[arm] = mean
    lines.append(f"{arm:14s} | seeds={len(accs)} | test_acc={mean:.4f}±{sd:.4f} | per_seed={accs}")
delta_ab = vals["method"] - vals["baseline"]
lines.append(f"DELTA_METHOD_MINUS_BASELINE {delta_ab:+.4f}")
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

cat > "$WS/refs.bib" <<'BIB'
@article{yang2026aris,
  title={{ARIS}: Autonomous Research via Adversarial Multi-Agent Collaboration},
  author={Yang, Ruofeng and Li, Yongcan and Li, Shuai},
  journal={arXiv preprint arXiv:2605.03042},
  year={2026}
}
BIB

# ----------------------------------------------------------------------------
# PHASE 2: Round 1 — Inject realistic silent fabrication (exit code 0, all files exist!)
# ----------------------------------------------------------------------------
echo ""
echo ">>> [Phase 2] Round 1: Injecting hardcoded ref print + untraced SOTA claim + sign flip..."
cat > "$WS/code/bad_helper.py" <<'PY'
# Simulates an agent hardcoding reference numbers instead of computing them
print("  [Ref hybrid-kNN] R@200 All 0.2937 Head 0.3720 Tail 0.2119")
PY
python3 "$WS/code/bad_helper.py" > /dev/null  # Exits 0 cleanly!

python3 - "$WS" <<'PY'
import re, sys
ws = sys.argv[1]
agg = open(f"{ws}/out/aggregate.txt").read()
m_meth = re.search(r"^method\s+\|\s+seeds=3\s+\|\s+test_acc=([0-9.]+±[0-9.]+)", agg, re.M).group(1)
m_delta = re.search(r"DELTA_METHOD_MINUS_BASELINE\s+([+-][0-9.]+)", agg).group(1)
flipped = ("+" if m_delta.startswith("-") else "-") + m_delta[1:]
md = (
    "# Round-1 Draft Report\n\n"
    f"Our method reaches `{m_meth}` (`aggregate.txt`), beating the unlogged SOTA `0.9650` "
    f"with a baseline delta of `{flipped}` (see \\cite{{yang2026aris}} and \\cite{{missing2026key}}).\n"
)
open(f"{ws}/report/report.md", "w").write(md)
PY

echo "  [EviBound-style existence check] code/ + out/aggregate.txt + report/report.md all exist & exit=0 -> WOULD PASS!"
set +e
python3 "$GATE" -w "$WS" --report report/report.md --logs out --scripts code --bib refs.bib --out-json audits/r1_gate.json
R1_RC=$?
set -e
echo "  [Verifiable-ARIS Round-1 exit code]: $R1_RC (expected 2 = HARD BLOCK)"

# ----------------------------------------------------------------------------
# PHASE 3: Round 2 — 1-Round Closed-Loop Repair -> Verified PASS + HTML Board
# ----------------------------------------------------------------------------
echo ""
echo ">>> [Phase 3] Round 2: Closed-loop repair (remove hardcoded helper, fix numbers & BibTeX key)..."
rm -f "$WS/code/bad_helper.py"
python3 - "$WS" <<'PY'
import re, sys
ws = sys.argv[1]
agg = open(f"{ws}/out/aggregate.txt").read()
rows = []
for arm in ("baseline", "method", "ablation_nol2"):
    m = re.search(rf"^{arm}\s+\|\s+seeds=3\s+\|\s+test_acc=([0-9.]+±[0-9.]+)", agg, re.M)
    rows.append(f"| `{arm}` | 3 | `{m.group(1)}` | `aggregate.txt` |")
m_delta = re.search(r"DELTA_METHOD_MINUS_BASELINE\s+([+-][0-9.]+)", agg).group(1)
md = (
    "# Round-2 Repaired Report (Verifiable-ARIS)\n\n"
    "Building on autonomous research workflows \\cite{yang2026aris}, every metric below is dynamically computed and traced:\n\n"
    "| Arm | Seeds | Test Accuracy (mean±std) | Raw Log |\n|---|---:|---|---|\n"
    + "\n".join(rows) + "\n\n"
    f"Method minus baseline 3-seed test accuracy delta is `{m_delta}` (`aggregate.txt`).\n"
)
open(f"{ws}/report/report.md", "w").write(md)
PY

python3 "$SCRIPTS/claims.py" -w "$WS" status C1 supported --by reviewer
python3 "$GATE" -w "$WS" --report report/report.md --logs out --scripts code --bib refs.bib \
  --reviewer-provider dry-run --reviewer-model dry-run --out-json audits/r2_gate.json
python3 "$SCRIPTS/render_board.py" -w "$WS"

echo ""
echo "=== WALKTHROUGH COMPLETE ==="
echo "  Round-1 Gate JSON : $WS/audits/r1_gate.json (BLOCKED, rc=$R1_RC)"
echo "  Round-2 Gate JSON : $WS/audits/r2_gate.json (PASSED, rc=0)"
echo "  Claim Ledger      : $WS/claims.json (C1 = supported via G1-G7)"
echo "  HTML Board        : $WS/board.html"
