# VeriLoop Real-GPU Deep Learning Showcase (`examples/gpu-dl-benchmark/`)

End-to-end verifiable deep learning trace executed on an **NVIDIA GeForce RTX 3060 Ti** (`PyTorch 2.9.1+cu128`, Fashion-MNIST, `4` architectures × `3` independent seeds = `12` GPU runs) demonstrating VeriLoop's 3-minute zero-transcription workflow:

1. **Multi-Format GPU Logging (`code/train_gpu_benchmark.py`):** Logs every run simultaneously to binary **TensorBoard** (`runs/tb/*/events.out.tfevents.*`), **Weights & Biases** local artifacts (`runs/wandb/*/files/wandb-{summary.json,history.jsonl}`), CSV (`runs/csv/`), and `out/gpu_runs.log`.
2. **Zero-Dependency Auto-Binding (`./veriloop bind`):** Parses TensorBoard + W&B logs with Python stdlib only and generates `paper/bound/bound_metrics.txt`, `bound_macros.tex`, `bound_table.tex`, `provenance_manifest.json`, `bound_curves.pdf`, and `bound_bars.pdf`.
3. **Authoritative BibTeX Fetching & Online Gate (`./veriloop fetch-bib` / `verify-cites`):** Fetches all 7 references (`paper/refs.bib`) directly from arXiv API and verifies titles, authors, years, and claim-vs-abstract grounding.
4. **Hard Evidence Gate + Interactive Web Review UI (`./veriloop gate` + `./veriloop review-ui`):** Verifies 100% traced numbers, 0 AST violations, 0 citation issues, compiles `paper/gpu_showcase.pdf`, and exports `review_ui.html` (click any metric in the paper to jump straight to the exact GPU log line!).

## Run It Yourself

```bash
# 5-second zero-GPU reproduction (re-binds committed RTX 3060 Ti logs -> PDF -> hard gate -> review_ui.html)
./veriloop gpu-showcase --skip-train

# Full GPU reproduction (re-trains all 12 PyTorch runs on your CUDA GPU -> ~6 min on RTX 3060 Ti)
VERILOOP_TORCH_PYTHON=/path/to/torch/python ./veriloop gpu-showcase

# Launch live interactive local Web Review UI on http://127.0.0.1:8765
./veriloop review-ui \
  --report examples/gpu-dl-benchmark/paper/gpu_showcase.tex examples/gpu-dl-benchmark/paper/bound/bound_table.tex \
  --logs examples/gpu-dl-benchmark/out/gpu_runs.log examples/gpu-dl-benchmark/paper/bound/bound_metrics.txt \
  --scripts examples/gpu-dl-benchmark/code/train_gpu_benchmark.py \
  --bib examples/gpu-dl-benchmark/paper/refs.bib \
  --serve --port 8765
```
