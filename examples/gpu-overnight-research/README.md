# VeriLoop Long-Horizon Real-GPU Case Study (42 RTX 3060 Ti Runs)

A complete, crash-resumable, zero-fabrication deep learning research trajectory executed end-to-end on a local **NVIDIA GeForce RTX 3060 Ti** (`torch 2.9.1+cu128`, AMP fp16, `5548.4s` / `92.47 min` GPU time, `593.0 MB` peak VRAM) under VeriLoop's full governance stack.

## What This Artifact Demonstrates

1. **Pre-registered Falsifiable Claims Ledger (`claims.json`)**: 4 hypotheses (`H1_ResidualGain`–`H4_CrossDatasetRank`) registered *before* GPU execution with explicit kill criteria, SHA-256 log hashes, and 7/7 mechanical gates (`G1–G7`, 0 post-evidence revisions).
2. **42 Real Multi-Seed GPU Runs Across 2 Benchmarks (`out/trajectory_ledger.jsonl`)**:
   - **CIFAR-10** (30 epochs, 45k/5k/10k split, 8 progressive methods × 3 seeds = **24 runs**): `M0_Linear` (`0.3692±0.0090`) → `M7_SEResNet_Full` (`0.9193±0.0004`, **+14.06 pp** over `M1_PlainCNN`).
   - **Fashion-MNIST** (15 epochs, 50k/10k/10k split, 6 core methods × 3 seeds = **18 runs**): `M0_Linear` (`0.8400±0.0011`) → `M5_ResNet_LS` (`0.9394±0.0004`) / `M4_ResNet_Aug_Cosine` (`0.9393±0.0013`) / `M7_SEResNet_Full` (`0.9373±0.0012`, **+3.75 pp** over `M1_PlainCNN`).
   - **Genuine Calibration Finding**: Unaugmented `M2_ResNet_Base` is severely overconfident (`raw_ece=0.1261 → cal_ece=0.0098` via validation-fitted `T*=2.6460`), whereas Label Smoothing (`T*=0.7234` C10 / `0.6716` FMNIST) and Mixup (`T*=0.6449` C10) flip predictions into underconfidence until validation-fitted `T*<1` restores sub-1.5% ECE.
3. **Live Persistent Research Wiki + Automated Per-Stage Gates (`wiki/RESEARCH_WIKI.md`, `out/gate_audit_trace.jsonl`)**:
   - **14/14 stage gates passed** (`1365` cumulative traced numbers, `0` untraced, `0` sign mismatches, `0` HIGH AST findings, median `81.8 ms` per gate, `$0` API cost).
4. **Zero-Transcription Log-to-LaTeX Binding (`paper/bound/cifar10/`, `paper/bound/fmnist/`)**:
   - `./veriloop bind` ingests 126 raw TensorBoard (`.tfevents`) and W&B files to emit `\vlC*` / `\vlF*` LaTeX macros, booktabs tables, provenance manifests, and Okabe-Ito vector PDFs.
5. **Verified Paper, Online Citations, Expanded-PDF Audit & Interactive Review UI**:
   - Compiled paper: `paper/overnight_study.pdf` (100% macro-bound, 10/10 arXiv/Crossref/S2 verified references).
   - Interactive split-pane audit view: `review_ui.html` (click any metric or citation to jump directly to the highlighted raw log line or fetched abstract).

## Reproduce End-to-End

```bash
bash examples/gpu-overnight-research/run_reproduce.sh
```
