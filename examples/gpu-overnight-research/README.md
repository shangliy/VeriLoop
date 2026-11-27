# VeriLoop Long-Horizon Real-GPU Case Study (42 RTX 3060 Ti Runs)

A complete, crash-resumable, zero-fabrication deep learning research trajectory executed end-to-end on a local **NVIDIA GeForce RTX 3060 Ti** (`torch 2.9.1+cu128`, AMP fp16, `5548.4s` / `92.47 min` GPU time, `593.0 MB` peak VRAM) under VeriLoop's full governance stack.

## What This Artifact Demonstrates

1. **Claims Ledger (`claims.json`, `audits/claims_check.txt`)**: 4 hypotheses (`H1_ResidualGain`–`H4_CrossDatasetRank`) registered before GPU execution (committed alongside results; production studies should anchor `claims.json` in a pre-run commit) passing 7/7 mechanical gates (`G1–G7`, 0 post-evidence revisions).
2. **42 Real Multi-Seed GPU Runs Across 2 Benchmarks (`out/trajectory_ledger.jsonl`)**:
   - **CIFAR-10** (30 epochs, 45k/5k/10k split, 8 bundled recipe stages × 3 seeds = **24 runs**): `M0_Linear` (`0.3692±0.0090`) → `M7_SEResNet_Full` (`0.9193±0.0004`, **+14.06 pp** over `M1_PlainCNN`).
   - **Fashion-MNIST** (15 epochs, 50k/10k/10k split, 6 core stages × 3 seeds = **18 runs**; Mixup omitted): `M0_Linear` (`0.8400±0.0011`) → `M5_ResNet_LS` (`0.9394±0.0004`) / `M4_ResNet_Aug_Cosine` (`0.9393±0.0013`) / `M7_SEResNet_Full` (`0.9373±0.0012`, **+3.75 pp** over `M1_PlainCNN`).
   - **Real Calibration Findings**: Unaugmented `M2_ResNet_Base` is strongly overconfident on CIFAR-10 (`raw_ece=0.1261 → cal_ece=0.0098`, `T*=2.6460`; milder on Fashion-MNIST, `T*=1.3368`). Label Smoothing flips to underconfidence on both datasets (`T*=0.7234` CIFAR-10 / `0.6716` Fashion-MNIST), and Mixup does likewise on CIFAR-10 (`T*=0.6449`), until validation-fitted `T*<1` restores calibrated ECE (`0.0061–0.0120` on CIFAR-10 `M4–M7`; note that on already well-calibrated Fashion-MNIST `M1_PlainCNN`, post-hoc `T*` slightly raises ECE from `0.0059` to `0.0069`).
3. **Live Persistent Research Wiki + Pipeline Self-Consistency Checks (`wiki/RESEARCH_WIKI.md`, `out/gate_audit_trace.jsonl`)**:
   - **14/14 stage checks passed** (`182` distinct numbers in the final wiki re-audited at each stage, `0` AST HIGH findings, median `81.8 ms` per stage, `$0` API cost — a live pipeline self-consistency and AST smoke check).
4. **Auto-Bound Log-to-LaTeX Tables & Macros (`paper/bound/cifar10/`, `paper/bound/fmnist/`)**:
   - `./veriloop bind` ingests 126 raw TensorBoard (`.tfevents`) and W&B files to emit `\vlC*` / `\vlF*` LaTeX macros for every per-arm metric and `temp_T` cell, Booktabs tables, provenance manifests, and Okabe-Ito vector PDFs (aggregate deltas and compute totals trace to `out/overnight_summary.txt`).
5. **Verified Paper, Committed Audit Logs (`audits/`) & Interactive Review UI**:
   - Compiled paper: `paper/overnight_study.pdf` + committed audit artifacts (`audits/veriloop_gate.json`, `audits/pdf_audit.json`, `audits/verify_cites_online.json`, `audits/claims_check.txt`) + split-pane `review_ui.html`.

## Reproduce End-to-End

```bash
bash examples/gpu-overnight-research/run_reproduce.sh
```
