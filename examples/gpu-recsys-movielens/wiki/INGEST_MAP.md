# VeriLoop Ingest Map — Paper Formulas ↔ Codebase AST Alignment

- **Generated (UTC):** `2026-11-27T07:17:05Z`
- **Papers Ingested:** `2`
- **AST Symbols Indexed:** `11`
- **Formula ↔ Code Alignments:** `26` (Unmatched watchlist: `0`)

## 1. Ingested Papers & Extracted Structure

### `2002.02126` — LightGCN: Simplifying and Powering Graph Convolution Network for Recommendation
- **Linked GitHub Repos:** https://github.com/dawenl/vae_cf, https://github.com/gusye1234/pytorch-light-gcn, https://github.com/kuandeng/LightGCN, https://github.com/xiangwang1223/neural_graph_collaborative_filtering
- **Extracted Hyperparameters:** learning_rate=0.001,19-; batch_size=1024; epochs=1000,20

### `2112.08679` — Are Graph Augmentations Necessary? Simple Graph Contrastive Learning for Recommendation
- **Linked GitHub Repos:** https://github.com/Coder-Yu/QRec
- **Extracted Hyperparameters:** learning_rate=0.001; epochs=3,30,50; dropout=0.1,0.9

## 2. Formula / Method ↔ Code Alignment Table

| Paper | Equation ID | LaTeX Location | Matched AST Symbol | Code `file:line` | Score | Shared Tokens |
|---|---|---|---|---|---:|---|
| `2002.02126` | `eq:NGCF` | `2_preliminary.tex:L7` | `LightGCNModel` (nn_module) | `train_recsys.py:L154` | 0.98 | `embedding, item, layers, propagate, propagation` |
| `2002.02126` | `eq_2` | `3_method_new.tex:L16` | `LightGCNModel` (nn_module) | `train_recsys.py:L154` | 0.39 | `gcn, neighborhood` |
| `2002.02126` | `eq:LGC` | `3_method_new.tex:L35` | `LightGCNModel` (nn_module) | `train_recsys.py:L154` | 1.10 | `gcn, in, light, propagation` |
| `2002.02126` | `eq_4` | `3_method_new.tex:L49` | `LightGCNModel` (nn_module) | `train_recsys.py:L154` | 1.11 | `embedding, final, in, item, items` |
| `2002.02126` | `eq_5` | `3_method_new.tex:L60` | `load_movielens_100k` (function) | `train_recsys.py:L47` | 0.97 | `as, defined, is, item` |
| `2002.02126` | `eq_6` | `3_method_new.tex:L66` | `MFModel` (nn_module) | `train_recsys.py:L142` | 0.93 | `embedding, item, items, user, users` |
| `2002.02126` | `eq_7` | `3_method_new.tex:L75` | `build_bipartite_norm_adj` (function) | `train_recsys.py:L108` | 0.78 | `adjacency, in, matrix, row` |
| `2002.02126` | `eq:E_LGCN` | `3_method_new.tex:L79` | `build_bipartite_norm_adj` (function) | `train_recsys.py:L108` | 0.93 | `adjacency, in, matrix, normalized, row` |
| `2002.02126` | `eq_9` | `3_method_new.tex:L95` | `load_movielens_100k` (function) | `train_recsys.py:L47` | 0.68 | `as, defined, in, is` |
| `2002.02126` | `eq:SGCN` | `3_method_new.tex:L100` | `load_movielens_100k` (function) | `train_recsys.py:L47` | 0.47 | `as, in, is` |
| `2002.02126` | `eq_11` | `3_method_new.tex:L111` | `load_movielens_100k` (function) | `train_recsys.py:L47` | 0.65 | `as, defined, in, is` |
| `2002.02126` | `eq_12` | `3_method_new.tex:L115` | `LightGCNModel` (nn_module) | `train_recsys.py:L154` | 1.46 | `embedding, final, gcn, in, layer` |
| `2002.02126` | `eq_13` | `3_method_new.tex:L129` | `LightGCNModel` (nn_module) | `train_recsys.py:L154` | 1.03 | `gcn, if, items, layer, light` |
| `2002.02126` | `eq:c_vu` | `3_method_new.tex:L135` | `evaluate_full_ranking` (function) | `train_recsys.py:L180` | 0.55 | `if, items, target` |
| `2002.02126` | `eq_15` | `3_method_new.tex:L145` | `bpr_ranking_loss` (function) | `train_recsys.py:L126` | 1.66 | `bayesian, bpr, loss, pairwise, personalized` |
| `2002.02126` | `eq_16` | `4_experiment.tex:L78` | `bpr_ranking_loss` (function) | `train_recsys.py:L126` | 0.94 | `bpr, loss` |
| `2002.02126` | `eq_17` | `4_experiment.tex:L212` | `LightGCNModel` (nn_module) | `train_recsys.py:L154` | 1.22 | `embedding, gcn, in, item, light` |
| `2112.08679` | `joint` | `paper.tex:L167` | `simgcl_infonce_loss` (function) | `train_recsys.py:L133` | 0.94 | `info, loss, nce, two` |
| `2112.08679` | `loss:cl` | `paper.tex:L172` | `simgcl_infonce_loss` (function) | `train_recsys.py:L133` | 1.12 | `info, loss, nce, two` |
| `2112.08679` | `lightgcn` | `paper.tex:L177` | `LightGCNModel` (nn_module) | `train_recsys.py:L154` | 0.93 | `gcn, item, layers, light` |
| `2112.08679` | `loss:cl2` | `paper.tex:L211` | `load_movielens_100k` (function) | `train_recsys.py:L47` | 0.51 | `in, is, item` |
| `2112.08679` | `bpr` | `paper.tex:L239` | `LightGCNModel` (nn_module) | `train_recsys.py:L154` | 0.99 | `gcn, in, layers, light` |
| `2112.08679` | `eq_6` | `paper.tex:L246` | `simgcl_infonce_loss` (function) | `train_recsys.py:L133` | 0.71 | `between, loss` |
| `2112.08679` | `eq_7` | `paper.tex:L268` | `LightGCNModel` (nn_module) | `train_recsys.py:L154` | 0.71 | `embedding, in, noise` |
| `2112.08679` | `eq_8` | `paper.tex:L275` | `LightGCNModel` (nn_module) | `train_recsys.py:L154` | 0.95 | `embedding, final, in, layer, perturbed` |
| `2112.08679` | `metric` | `paper.tex:L286` | `build_bipartite_norm_adj` (function) | `train_recsys.py:L108` | 0.64 | `in, items, normalized, users` |
