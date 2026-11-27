# VeriLoop Level-2 Verified Research Report

- **Hypothesis (`C1_Primary`):** Targeted algorithmic refinement addressing unverified/unmatched formulation eq_9 in 1810.00826 across reference study (Semi-Supervised Classification with Graph Convolutional Networks; How Powerful are Graph Neural Networks?) improves held-out evaluation metrics over the baseline under strict validation-only selection.
- **Selection Protocol:** Validation-only checkpoint selection; zero manual metric overrides.

## Bound Experimental Results

Source: `paper/bound/bound_metrics.txt`

- `BOUND M0_MLP | best_epoch | n=5 | 180.8000±25.0140 [149.7460,211.8540] | s42=188.0000 s43=187.0000 s44=137.0000 s45=200.0000 s46=192.0000`
- `BOUND M0_MLP | dirichlet_energy | n=5 | 0.0792±0.0036 [0.0747,0.0836] | pct=7.92±0.36% | s42=0.0760 s43=0.0851 s44=0.0795 s45=0.0769 s46=0.0784`
- `BOUND M0_MLP | elapsed_s | n=5 | 1.0916±0.1122 [0.9523,1.2309] | s42=1.1300 s43=0.9220 s44=1.1750 s45=1.1930 s46=1.0380`
- `BOUND M0_MLP | test_acc | n=5 | 0.5968±0.0048 [0.5908,0.6028] | pct=59.68±0.48% | s42=0.5970 s43=0.6010 s44=0.5930 s45=0.6020 s46=0.5910`
- `BOUND M0_MLP | test_ece | n=5 | 0.1607±0.0082 [0.1506,0.1709] | s42=0.1571 s43=0.1621 s44=0.1718 s45=0.1631 s46=0.1496`
- `BOUND M0_MLP | val_acc | n=5 | 0.5852±0.0073 [0.5761,0.5943] | pct=58.52±0.73% | s42=0.5880 s43=0.5740 s44=0.5860 s45=0.5840 s46=0.5940`
- `BOUND M1_GCN_2L | best_epoch | n=5 | 118.8000±52.9122 [53.1114,184.4886] | s42=125.0000 s43=112.0000 s44=192.0000 s45=122.0000 s46=43.0000`
- `BOUND M1_GCN_2L | dirichlet_energy | n=5 | 0.0264±0.0072 [0.0174,0.0353] | pct=2.64±0.72% | s42=0.0323 s43=0.0288 s44=0.0144 s45=0.0312 s46=0.0251`
- `BOUND M1_GCN_2L | elapsed_s | n=5 | 1.3208±0.1058 [1.1895,1.4521] | s42=1.3900 s43=1.3610 s44=1.2650 s45=1.4240 s46=1.1640`
- `BOUND M1_GCN_2L | test_acc | n=5 | 0.7980±0.0432 [0.7444,0.8516] | pct=79.80±4.32% | s42=0.8150 s43=0.8230 s44=0.7210 s45=0.8160 s46=0.8150`
- `BOUND M1_GCN_2L | test_ece | n=5 | 0.1830±0.0303 [0.1454,0.2207] | s42=0.1614 s43=0.1983 s44=0.1683 s45=0.1579 s46=0.2292`
- `BOUND M1_GCN_2L | val_acc | n=5 | 0.7908±0.0351 [0.7472,0.8344] | pct=79.08±3.51% | s42=0.8060 s43=0.8080 s44=0.7280 s45=0.8080 s46=0.8040`
- `BOUND M2_GCN_8L_Deep | best_epoch | n=5 | 85.0000±88.4816 [-24.8468,194.8468] | s42=196.0000 s43=22.0000 s44=166.0000 s45=29.0000 s46=12.0000`
- `BOUND M2_GCN_8L_Deep | dirichlet_energy | n=5 | 0.0023±0.0021 [-0.0003,0.0049] | pct=0.23±0.21% | s42=0.0011 s43=0.0011 s44=0.0034 s45=0.0054 s46=0.0005`
- `BOUND M2_GCN_8L_Deep | elapsed_s | n=5 | 3.5672±0.4723 [2.9808,4.1536] | s42=3.8210 s43=3.5710 s44=3.0980 s45=3.1320 s46=4.2140`
- `BOUND M2_GCN_8L_Deep | test_acc | n=5 | 0.2358±0.0022 [0.2331,0.2385] | pct=23.58±0.22% | s42=0.2390 s43=0.2340 s44=0.2340 s45=0.2370 s46=0.2350`
- `BOUND M2_GCN_8L_Deep | test_ece | n=5 | 0.0756±0.0116 [0.0611,0.0900] | s42=0.0634 s43=0.0826 s44=0.0625 s45=0.0865 s46=0.0828`
- `BOUND M2_GCN_8L_Deep | val_acc | n=5 | 0.2328±0.0105 [0.2197,0.2459] | pct=23.28±1.05% | s42=0.2380 s43=0.2380 s44=0.2140 s45=0.2380 s46=0.2360`
- `BOUND M3_APPNP_PPR | best_epoch | n=5 | 77.8000±23.3388 [48.8257,106.7743] | s42=119.0000 s43=71.0000 s44=62.0000 s45=71.0000 s46=66.0000`
- `BOUND M3_APPNP_PPR | dirichlet_energy | n=5 | 0.0475±0.0079 [0.0378,0.0573] | pct=4.75±0.79% | s42=0.0497 s43=0.0507 s44=0.0553 s45=0.0344 s46=0.0475`
- `BOUND M3_APPNP_PPR | elapsed_s | n=5 | 1.7268±0.5496 [1.0445,2.4091] | s42=2.6920 s43=1.5630 s44=1.3300 s45=1.4520 s46=1.5970`
- `BOUND M3_APPNP_PPR | test_acc | n=5 | 0.8348±0.0050 [0.8286,0.8410] | pct=83.48±0.50% | s42=0.8320 s43=0.8390 s44=0.8330 s45=0.8410 s46=0.8290`
- `BOUND M3_APPNP_PPR | test_ece | n=5 | 0.2351±0.0500 [0.1730,0.2972] | s42=0.1935 s43=0.1859 s44=0.2808 s45=0.2948 s46=0.2206`
- `BOUND M3_APPNP_PPR | val_acc | n=5 | 0.8112±0.0011 [0.8098,0.8126] | pct=81.12±0.11% | s42=0.8120 s43=0.8100 s44=0.8120 s45=0.8120 s46=0.8100`
- `BOUND M4_GCNII_8L | best_epoch | n=5 | 131.0000±56.5420 [60.8051,201.1949] | s42=82.0000 s43=64.0000 s44=172.0000 s45=195.0000 s46=142.0000`
- `BOUND M4_GCNII_8L | dirichlet_energy | n=5 | 0.0000±0.0000 [0.0000,0.0000] | pct=0.00±0.00% | s42=0.0000 s43=0.0000 s44=0.0000 s45=0.0000 s46=0.0000`
- `BOUND M4_GCNII_8L | elapsed_s | n=5 | 3.9848±1.1414 [2.5678,5.4018] | s42=2.5930 s43=3.0270 s44=4.3010 s45=4.6940 s46=5.3090`
- `BOUND M4_GCNII_8L | test_acc | n=5 | 0.2460±0.0320 [0.2063,0.2857] | pct=24.60±3.20% | s42=0.2210 s43=0.2930 s44=0.2620 s45=0.2390 s46=0.2150`
- `BOUND M4_GCNII_8L | test_ece | n=5 | 0.0830±0.0412 [0.0318,0.1342] | s42=0.0532 s43=0.1490 s44=0.0944 s45=0.0714 s46=0.0471`
- `BOUND M4_GCNII_8L | val_acc | n=5 | 0.2804±0.0166 [0.2598,0.3010] | pct=28.04±1.66% | s42=0.2580 s43=0.3000 s44=0.2900 s45=0.2840 s46=0.2700`
- `BOUND sandbox_runs | elapsed_s | n=1 | 175.1700±0.0000 [175.1700,175.1700] | s0=175.1700`
- `BOUND sandbox_runs | log_bytes | n=1 | 2329.0000±0.0000 [2329.0000,2329.0000] | s0=2329.0000`
- `BOUND sandbox_runs | returncode | n=1 | 0.0000±0.0000 [0.0000,0.0000] | pct=0.00±0.00% | s0=0.0000`

## References

Ingested arXiv formulations aligned via Python AST (`wiki/INGEST_MAP.md`): GCN \cite{kipf2016semi}, GIN expressiveness \cite{xu2018powerful}, and GCNII deep residual propagation \cite{chen2020simple}.
