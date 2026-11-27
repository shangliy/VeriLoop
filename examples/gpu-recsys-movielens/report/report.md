# VeriLoop Level-2 Verified Research Report

- **Hypothesis (`C1_Primary`):** Targeted algorithmic refinement addressing calibration, generalization, and reproducibility gaps across reference methods across reference study (LightGCN: Simplifying and Powering Graph Convolution Network for Recommendation; Are Graph Augmentations Necessary? Simple Graph Contrastive Learning for Recommendation) improves held-out evaluation metrics over the baseline under strict validation-only selection.
- **Selection Protocol:** Validation-only checkpoint selection; zero manual metric overrides.

## Bound Experimental Results

Source: `paper/bound/bound_metrics.txt`

- `BOUND R0_Pop | best_epoch | n=1 | 0.0000±0.0000 [0.0000,0.0000] | pct=0.00±0.00% | s42=0.0000`
- `BOUND R0_Pop | elapsed_s | n=1 | 0.0100±0.0000 [0.0100,0.0100] | pct=1.00±0.00% | s42=0.0100`
- `BOUND R0_Pop | test_ndcg10 | n=3 | 0.0406±0.0000 [0.0406,0.0406] | pct=4.06±0.00% | s42=0.0406 s43=0.0406 s44=0.0406`
- `BOUND R0_Pop | test_ndcg20 | n=3 | 0.0545±0.0000 [0.0545,0.0545] | pct=5.45±0.00% | s42=0.0545 s43=0.0545 s44=0.0545`
- `BOUND R0_Pop | test_recall10 | n=3 | 0.0810±0.0000 [0.0810,0.0810] | pct=8.10±0.00% | s42=0.0810 s43=0.0810 s44=0.0810`
- `BOUND R0_Pop | test_recall20 | n=3 | 0.1365±0.0000 [0.1365,0.1365] | pct=13.65±0.00% | s42=0.1365 s43=0.1365 s44=0.1365`
- `BOUND R0_Pop | val_ndcg20 | n=3 | 0.0475±0.0000 [0.0475,0.0475] | pct=4.75±0.00% | s42=0.0475 s43=0.0475 s44=0.0475`
- `BOUND R1_MF_BPR | best_epoch | n=3 | 46.6667±7.6376 [27.6922,65.6411] | s42=55.0000 s43=45.0000 s44=40.0000`
- `BOUND R1_MF_BPR | elapsed_s | n=3 | 26.0233±3.6876 [16.8621,35.1846] | s42=26.7400 s43=22.0300 s44=29.3000`
- `BOUND R1_MF_BPR | test_ndcg10 | n=3 | 0.0611±0.0014 [0.0576,0.0645] | pct=6.11±0.14% | s42=0.0622 s43=0.0615 s44=0.0595`
- `BOUND R1_MF_BPR | test_ndcg20 | n=3 | 0.0788±0.0016 [0.0749,0.0827] | pct=7.88±0.16% | s42=0.0805 s43=0.0785 s44=0.0774`
- `BOUND R1_MF_BPR | test_recall10 | n=3 | 0.1237±0.0038 [0.1142,0.1331] | pct=12.37±0.38% | s42=0.1226 s43=0.1279 s44=0.1205`
- `BOUND R1_MF_BPR | test_recall20 | n=3 | 0.1948±0.0016 [0.1907,0.1988] | pct=19.48±0.16% | s42=0.1951 s43=0.1962 s44=0.1930`
- `BOUND R1_MF_BPR | val_ndcg20 | n=3 | 0.0814±0.0019 [0.0767,0.0862] | pct=8.14±0.19% | s42=0.0807 s43=0.0800 s44=0.0836`
- `BOUND R2_LightGCN | best_epoch | n=3 | 58.3333±2.8868 [51.1617,65.5050] | s42=55.0000 s43=60.0000 s44=60.0000`
- `BOUND R2_LightGCN | elapsed_s | n=3 | 44.0333±5.9719 [29.1971,58.8695] | s42=50.8100 s43=39.5400 s44=41.7500`
- `BOUND R2_LightGCN | test_ndcg10 | n=3 | 0.0552±0.0003 [0.0545,0.0559] | pct=5.52±0.03% | s42=0.0555 s43=0.0549 s44=0.0552`
- `BOUND R2_LightGCN | test_ndcg20 | n=3 | 0.0738±0.0017 [0.0697,0.0779] | pct=7.38±0.17% | s42=0.0754 s43=0.0740 s44=0.0721`
- `BOUND R2_LightGCN | test_recall10 | n=3 | 0.1166±0.0022 [0.1111,0.1220] | pct=11.66±0.22% | s42=0.1141 s43=0.1173 s44=0.1183`
- `BOUND R2_LightGCN | test_recall20 | n=3 | 0.1905±0.0043 [0.1797,0.2013] | pct=19.05±0.43% | s42=0.1930 s43=0.1930 s44=0.1855`
- `BOUND R2_LightGCN | val_ndcg20 | n=3 | 0.0749±0.0007 [0.0733,0.0766] | pct=7.49±0.07% | s42=0.0755 s43=0.0751 s44=0.0742`
- `BOUND R3_SimGCL | best_epoch | n=3 | 60.0000±0.0000 [60.0000,60.0000] | s42=60.0000 s43=60.0000 s44=60.0000`
- `BOUND R3_SimGCL | elapsed_s | n=3 | 109.0633±18.0422 [64.2404,153.8863] | s42=119.4900 s43=88.2300 s44=119.4700`
- `BOUND R3_SimGCL | test_ndcg10 | n=3 | 0.0103±0.0012 [0.0073,0.0133] | pct=1.03±0.12% | s42=0.0095 s43=0.0117 s44=0.0097`
- `BOUND R3_SimGCL | test_ndcg20 | n=3 | 0.0130±0.0014 [0.0095,0.0164] | pct=1.30±0.14% | s42=0.0116 s43=0.0144 s44=0.0129`
- `BOUND R3_SimGCL | test_recall10 | n=3 | 0.0192±0.0039 [0.0096,0.0288] | pct=1.92±0.39% | s42=0.0160 s43=0.0235 s44=0.0181`
- `BOUND R3_SimGCL | test_recall20 | n=3 | 0.0298±0.0049 [0.0177,0.0420] | pct=2.98±0.49% | s42=0.0245 s43=0.0341 s44=0.0309`
- `BOUND R3_SimGCL | val_ndcg20 | n=3 | 0.0177±0.0038 [0.0083,0.0270] | pct=1.77±0.38% | s42=0.0137 s43=0.0212 s44=0.0181`
- `BOUND sandbox_runs | elapsed_s | n=1 | 550.7200±0.0000 [550.7200,550.7200] | s0=550.7200`
- `BOUND sandbox_runs | log_bytes | n=1 | 838.0000±0.0000 [838.0000,838.0000] | s0=838.0000`
- `BOUND sandbox_runs | returncode | n=1 | 0.0000±0.0000 [0.0000,0.0000] | pct=0.00±0.00% | s0=0.0000`

## References

Ingested arXiv formulations aligned via Python AST (`wiki/INGEST_MAP.md`): LightGCN \cite{he2020lightgcn} and SimGCL \cite{yu2021simgcl}.
