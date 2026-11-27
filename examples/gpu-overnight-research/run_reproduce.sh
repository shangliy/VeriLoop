#!/usr/bin/env bash
# End-to-end reproduction of VeriLoop's 42-run RTX 3060 Ti Real-GPU Research Study.
# Usage: bash examples/gpu-overnight-research/run_reproduce.sh
set -euo pipefail

WS="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$WS/../.." && pwd)"
PY="${VERILOOP_PYTHON:-$(command -v python3)}"

echo "[1/6] Running 42-run GPU study (CIFAR-10 30 ep + Fashion-MNIST 15 ep, 3 seeds each)..."
"$PY" "$WS/code/run_overnight_study.py" --ws "$WS" --data-root "${DATA_ROOT:-/tmp}" --datasets cifar10 fmnist --seeds 42 43 44 --resume

echo "[2/6] Binding TensorBoard/W&B logs -> LaTeX macros/tables & Okabe-Ito vector PDFs..."
"$PY" "$WS/code/analyze_and_plot.py"

echo "[3/6] Compiling overnight_study.pdf (ICML-style layout, 100% macro-bound)..."
(
  cd "$WS/paper"
  export TEXINPUTS=".:$ROOT/paper/icml2027:"
  export BIBINPUTS=".:$ROOT/paper/icml2027:"
  export BSTINPUTS=".:$ROOT/paper/icml2027:"
  pdflatex -interaction=nonstopmode -halt-on-error overnight_study.tex >/dev/null
  bibtex overnight_study >/dev/null
  pdflatex -interaction=nonstopmode -halt-on-error overnight_study.tex >/dev/null
  pdflatex -interaction=nonstopmode -halt-on-error overnight_study.tex >/dev/null
)

echo "[4/6] Running VeriLoop hard verifiable gate + online citation audit + claims check (logging to audits/)..."
mkdir -p "$WS/audits"
"$ROOT/veriloop" claims -w "$WS" check | tee "$WS/audits/claims_check.txt"
"$ROOT/veriloop" verify-cites "$WS/paper/overnight_study.tex" --bib "$WS/paper/refs.bib" --online --check-claims --json > "$WS/audits/verify_cites_online.json"
"$ROOT/veriloop" gate \
  --workspace "$WS" \
  --report "$WS/paper/overnight_study.tex" \
  --logs "$WS/out/overnight_summary.txt" "$WS/out/wiki_metrics.log" \
         "$WS/paper/bound/cifar10/bound_metrics.txt" "$WS/paper/bound/fmnist/bound_metrics.txt" \
  --scripts "$WS/code" \
  --bib "$WS/paper/refs.bib" \
  --online-cites \
  --check-claims \
  --out-json "$WS/audits/veriloop_gate.json"

echo "[5/6] Auditing compiled PDF (expanded-macro number tracing, fonts, layout -> audits/pdf_audit.json)..."
"$ROOT/veriloop" audit-pdf "$WS/paper/overnight_study.pdf" \
  --logs "$WS/out/overnight_summary.txt" \
         "$WS/paper/bound/cifar10/bound_metrics.txt" "$WS/paper/bound/fmnist/bound_metrics.txt" \
  --json > "$WS/audits/pdf_audit.json"

echo "[6/6] Building interactive split-pane Review UI..."
"$ROOT/veriloop" review-ui \
  --report "$WS/paper/overnight_study.tex" \
  --logs "$WS/out/overnight_summary.txt" "$WS/out/wiki_metrics.log" \
         "$WS/paper/bound/cifar10/bound_metrics.txt" "$WS/paper/bound/fmnist/bound_metrics.txt" \
  --scripts "$WS/code" \
  --bib "$WS/paper/refs.bib" \
  --out "$WS/review_ui.html"

echo "REPRODUCTION_COMPLETE -> $WS/paper/overnight_study.pdf & $WS/review_ui.html"
