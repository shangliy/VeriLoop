#!/usr/bin/env bash
# VeriLoop 3-Minute End-to-End GPU Deep Learning -> Paper Showcase
# Usage:
#   ./veriloop gpu-showcase               # full run (train on GPU + bind + PDF + hard gate + Web UI)
#   ./veriloop gpu-showcase --skip-train  # 5-second zero-GPU re-bind, PDF build, hard gate & Web UI
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WS="$ROOT/examples/gpu-dl-benchmark"
SKIP_TRAIN=0
if [[ "${1:-}" == "--skip-train" ]]; then
  SKIP_TRAIN=1
fi

echo "=== [1/5] GPU Deep Learning Training (Fashion-MNIST, 4 models x 3 seeds) ==="
if [[ "$SKIP_TRAIN" -eq 0 ]]; then
  PY="${VERILOOP_TORCH_PYTHON:-python3}"
  "$PY" "$WS/code/train_gpu_benchmark.py" --out-root "$WS" --epochs 8 --seeds 42 43 44
else
  echo "  (--skip-train: reusing committed RTX 3060 Ti TensorBoard, W&B, and CSV logs)"
fi

echo "=== [2/5] Auto-Bind TensorBoard + W&B Logs -> LaTeX Macros, Booktabs & Okabe-Ito PDFs ==="
python3 "$ROOT/tools/paper_bind.py" \
  --inputs "$WS/runs/tb" "$WS/runs/wandb" \
  --metrics val_acc test_acc test_loss \
  --curve-metric val_acc \
  --out-dir "$WS/paper/bound"

echo "=== [3/5] Compile 100%-Bound Conference Paper PDF ==="
if command -v pdflatex >/dev/null 2>&1; then
  (
    cd "$WS/paper"
    TEXINPUTS=".:$ROOT/paper/icml2027:" pdflatex -interaction=nonstopmode gpu_showcase.tex >/dev/null
    BIBINPUTS=".:$ROOT/paper/icml2027:" BSTINPUTS=".:$ROOT/paper/icml2027:" bibtex gpu_showcase >/dev/null
    TEXINPUTS=".:$ROOT/paper/icml2027:" pdflatex -interaction=nonstopmode gpu_showcase.tex >/dev/null
    TEXINPUTS=".:$ROOT/paper/icml2027:" pdflatex -interaction=nonstopmode gpu_showcase.tex >/dev/null
    rm -f gpu_showcase.aux gpu_showcase.bbl gpu_showcase.blg gpu_showcase.log gpu_showcase.out
  )
  echo "  Compiled: $WS/paper/gpu_showcase.pdf"
else
  echo "  (pdflatex not found; skipping PDF build)"
fi

echo "=== [4/5] Enforce VeriLoop Dual-Layer Hard Evidence Gate (Numbers + AST + Claims + BibTeX) ==="
python3 "$ROOT/tools/verifiable_gate.py" \
  --workspace "$WS" \
  --report paper/gpu_showcase.tex \
  --logs out paper/bound/bound_metrics.txt \
  --scripts code \
  --bib paper/refs.bib \
  --out-json audits/gpu_showcase_gate.json

echo "=== [5/5] Build Interactive Local Web Review UI (click any number -> exact GPU log line) ==="
python3 "$ROOT/tools/review_ui.py" \
  --report "$WS/paper/gpu_showcase.tex" "$WS/paper/bound/bound_table.tex" \
  --logs "$WS/out/gpu_runs.log" "$WS/paper/bound/bound_metrics.txt" \
  --scripts "$WS/code/train_gpu_benchmark.py" \
  --bib "$WS/paper/refs.bib" \
  --out "$WS/review_ui.html"

echo ""
echo "SHOWCASE COMPLETE! Open $WS/review_ui.html in any browser (or pass --serve to ./veriloop review-ui)."
