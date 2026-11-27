# VeriLoop Ingest Map — Paper Formulas ↔ Codebase AST Alignment

- **Generated (UTC):** `2026-11-27T07:13:18Z`
- **Papers Ingested:** `3`
- **AST Symbols Indexed:** `17`
- **Formula ↔ Code Alignments:** `49` (Unmatched watchlist: `10`)

## 1. Ingested Papers & Extracted Structure

### `1609.02907` — Semi-Supervised Classification with Graph Convolutional Networks
- **Authors:** Thomas N. Kipf, Max Welling
- **Year:** 2016 | **Equations:** `14` | **Sections:** `26`
- **Linked GitHub Repos:** https://github.com/kimiyoung/planetoid, https://github.com/tkipf/gcn
- **Extracted Hyperparameters:** learning_rate=2017; epochs=100,200,400

### `1810.00826` — How Powerful are Graph Neural Networks?
- **Authors:** Keyulu Xu, Weihua Hu, Jure Leskovec, Stefanie Jegelka
- **Year:** 2018 | **Equations:** `23` | **Sections:** `25`
- **Linked GitHub Repos:** https://github.com/weihua916/powerful-gnns
- **Extracted Hyperparameters:** learning_rate=2019; epochs=50

### `2007.02133` — Simple and Deep Graph Convolutional Networks
- **Authors:** Ming Chen, Zhewei Wei, Zengfeng Huang, Bolin Ding, Yaliang Li
- **Year:** 2020 | **Equations:** `22` | **Sections:** `19`
- **Linked GitHub Repos:** https://github.com/DropEdge/DropEdge, https://github.com/chennnM/GCNII
- **Extracted Hyperparameters:** learning_rate=0.001.,0.01; epochs=100; dropout=0.5,0.6,0.7

## 2. Formula / Method ↔ Code Alignment Table

| Paper | Equation ID | LaTeX Location | Matched AST Symbol | Code `file:line` | Score | Shared Tokens |
|---|---|---|---|---|---:|---|
| `1609.02907` | `eq:graph-reg` | `main.tex:L52` | `GCNModel` (nn_module) | `train_gnn.py:L184` | 0.49 | `graph, in, network` |
| `1609.02907` | `eq:gcn-layer` | `main.tex:L66` | `GCNModel` (nn_module) | `train_gnn.py:L184` | 1.04 | `convolutional, graph, in, layer, multi` |
| `1609.02907` | `eq:fourier-conv` | `main.tex:L75` | `evaluate_node_classification` (function) | `train_gnn.py:L285` | 0.61 | `eq, node` |
| `1609.02907` | `eq:tchebyshew` | `main.tex:L80` | `compute_ece` (function) | `train_gnn.py:L157` | 0.51 | `eq, in, max` |
| `1609.02907` | `eq:fourier-conv-approx` | `main.tex:L87` | `_download_planetoid` (function) | `train_gnn.py:L47` | 0.42 | `as, is` |
| `1609.02907` | `eq:fourier-conv-approx2` | `main.tex:L100` | `GCNModel` (nn_module) | `train_gnn.py:L184` | 0.74 | `in, linear, network, training` |
| `1609.02907` | `eq:fourier-conv-approx3` | `main.tex:L109` | `train_one_run` (function) | `train_gnn.py:L296` | 0.65 | `eq, in, parameters, range` |
| `1609.02907` | `eq:fourier-conv-approx4` | `main.tex:L116` | `evaluate_node_classification` (function) | `train_gnn.py:L285` | 0.65 | `eq, node` |
| `1609.02907` | `eq:two-layer-gcn` | `main.tex:L147` | `evaluate_node_classification` (function) | `train_gnn.py:L285` | 1.17 | `classification, eq, hidden, node` |
| `1609.02907` | `eq:` | `main.tex:L152` | `evaluate_node_classification` (function) | `train_gnn.py:L285` | 1.67 | `classification, eq, evaluate, node` |
| `1609.02907` | `eq:trade-off-param` | `main.tex:L305` | `GCNModel` (nn_module) | `train_gnn.py:L184` | 0.47 | `graph, in, layers` |
| `1609.02907` | `eq:diff-model` | `main.tex:L346` | `evaluate_node_classification` (function) | `train_gnn.py:L285` | 0.76 | `edge, eq, node` |
| `1609.02907` | `eq:three-layer-gcn` | `main.tex:L358` | `GCNModel` (nn_module) | `train_gnn.py:L184` | 0.50 | `graph, in, layer` |
| `1609.02907` | `eq:gcn-residual-layer` | `main.tex:L448` | `GCNModel` (nn_module) | `train_gnn.py:L184` | 0.61 | `layer, layers, training` |
| `1810.00826` | `eq_1` | `appendix.tex:L62` | `set_seed` (function) | `train_gnn.py:L39` | 0.84 | `if, is, set` |
| `1810.00826` | `eq_2` | `appendix.tex:L73` | `_download_planetoid` (function) | `train_gnn.py:L47` | 0.77 | `as, if, is, size` |
| `1810.00826` | `eq:rewrite` | `appendix.tex:L94` | `_download_planetoid` (function) | `train_gnn.py:L47` | 0.40 | `as, is` |
| `1810.00826` | `eq_4` | `appendix.tex:L12` | `train_one_run` (function) | `train_gnn.py:L296` | 0.89 | `eq, features, if, on` |
| `1810.00826` | `eq_5` | `appendix.tex:L14` | `train_one_run` (function) | `train_gnn.py:L296` | 0.92 | `eq, features, in, on` |
| `1810.00826` | `eq_6` | `appendix.tex:L15` | `train_one_run` (function) | `train_gnn.py:L296` | 0.52 | `eq, features` |
| `1810.00826` | `eq_7` | `appendix.tex:L23` | `evaluate_node_classification` (function) | `train_gnn.py:L285` | 0.59 | `eq, node` |
| `1810.00826` | `eq_8` | `appendix.tex:L25` | `evaluate_node_classification` (function) | `train_gnn.py:L285` | 0.73 | `eq, node` |
| `1810.00826` | `eq_12` | `appendix.tex:L68` | `set_seed` (function) | `train_gnn.py:L39` | 1.11 | `is, set` |
| `1810.00826` | `eq_13` | `appendix.tex:L111` | `_download_planetoid` (function) | `train_gnn.py:L47` | 0.47 | `as, or` |
| `1810.00826` | `eq_14` | `appendix.tex:L112` | `_download_planetoid` (function) | `train_gnn.py:L47` | 0.58 | `as, or` |
| `1810.00826` | `eq_15` | `appendix.tex:L120` | `set_seed` (function) | `train_gnn.py:L39` | 1.01 | `is, set` |
| `1810.00826` | `eq_16` | `appendix.tex:L128` | `set_seed` (function) | `train_gnn.py:L39` | 0.82 | `is, set` |
| `1810.00826` | `GIN-agg` | `method.tex:L78` | `_download_planetoid` (function) | `train_gnn.py:L47` | 0.95 | `as, exist, if, in, is` |
| `1810.00826` | `eq_19` | `method.tex:L32` | `train_one_run` (function) | `train_gnn.py:L296` | 0.87 | `eq, features, in, on` |
| `1810.00826` | `eq:combine` | `preliminary.tex:L13` | `set_seed` (function) | `train_gnn.py:L39` | 0.59 | `is, set` |
| `1810.00826` | `eq:graphsage-agg` | `preliminary.tex:L24` | `load_planetoid_dataset` (function) | `train_gnn.py:L66` | 0.73 | `graph, in, matrix, max` |
| `1810.00826` | `eq:gcn-agg` | `preliminary.tex:L31` | `GCNModel` (nn_module) | `train_gnn.py:L184` | 0.69 | `convolutional, graph, in, linear` |
| `1810.00826` | `eq:graph_pool` | `preliminary.tex:L37` | `evaluate_node_classification` (function) | `train_gnn.py:L285` | 1.08 | `classification, eq, node` |
| `2007.02133` | `eqn:gcn_res` | `analysis.tex:L6` | `GCNModel` (nn_module) | `train_gnn.py:L184` | 0.67 | `graph, layer, multi` |
| `2007.02133` | `eqn:GCN_THM` | `analysis.tex:L43` | `main` (function) | `train_gnn.py:L348` | 0.67 | `gcn, is` |
| `2007.02133` | `eq_3` | `analysis.tex:L81` | `evaluate_node_classification` (function) | `train_gnn.py:L285` | 0.70 | `eq, node` |
| `2007.02133` | `eq_4` | `appendix.tex:L11` | `GCNIILayer` (nn_module) | `train_gnn.py:L236` | 0.61 | `gcnii, parameter, weight` |
| `2007.02133` | `eq_5` | `appendix.tex:L19` | `_download_planetoid` (function) | `train_gnn.py:L47` | 0.52 | `as, is` |
| `2007.02133` | `eq_7` | `appendix.tex:L39` | `train_one_run` (function) | `train_gnn.py:L296` | 0.50 | `eq, on` |
| `2007.02133` | `eq_12` | `appendix.tex:L165` | `_download_planetoid` (function) | `train_gnn.py:L47` | 0.58 | `as, or` |
| `2007.02133` | `eq_14` | `experiments.tex:L52` | `GCNIILayer` (nn_module) | `train_gnn.py:L236` | 1.00 | `gcnii, initial, layer, residual, weight` |
| `2007.02133` | `eqn:gcnii_analysis` | `model.tex:L15` | `GCNIILayer` (nn_module) | `train_gnn.py:L236` | 1.20 | `gcnii, identity, initial, layer, mapping` |
| `2007.02133` | `eqn:gcn` | `pre.tex:L22` | `gcn_normalized_adjacency` (function) | `train_gnn.py:L136` | 1.44 | `gcn, normalized` |
| `2007.02133` | `eqn:ppnp` | `pre.tex:L34` | `appnp_ppr_propagate` (function) | `train_gnn.py:L210` | 0.88 | `appnp, page, personalized, rank` |
| `2007.02133` | `eqn:APPNP` | `pre.tex:L40` | `appnp_ppr_propagate` (function) | `train_gnn.py:L210` | 0.66 | `appnp, propagation` |
| `2007.02133` | `eqn:dropgcn` | `pre.tex:L53` | `set_seed` (function) | `train_gnn.py:L39` | 0.39 | `is, random` |
| `2007.02133` | `eq_20` | `ridge.tex:L3` | `_download_planetoid` (function) | `train_gnn.py:L47` | 0.49 | `as, in, is` |
| `2007.02133` | `eq_21` | `ridge.tex:L7` | `_download_planetoid` (function) | `train_gnn.py:L47` | 0.56 | `in, is, size` |
| `2007.02133` | `eq_22` | `ridge.tex:L11` | `train_one_run` (function) | `train_gnn.py:L296` | 1.21 | `eq, if, in, lr, one` |

## 3. Layer-2 Verification Watchlist (Unmatched Equations)

Equations below had no direct AST symbol match; Layer-2 auditors should verify they are genuinely implemented (not stubbed or omitted):

- `1810.00826` `eq_9` (`appendix.tex:L27`): `h_v^{(k)} = \phi \left( \varphi \left( l_v^{(k-1)} \right), f \left( \left\lbrace \varphi \left( l_u^{(k-1)} \`
- `1810.00826` `eq_10` (`appendix.tex:L29`): `h_v^{(k)} = \psi \left( l_v^{(k-1)}, \left\lbrace l_u^{(k-1)}: u \in \mathcal{N}(v) \right\rbrace \right)`
- `1810.00826` `eq_11` (`appendix.tex:L31`): `h_v^{(k)} = \psi \circ g^{-1} g \left( l_v^{(k-1)}, \left\lbrace l_u^{(k-1)}: u \in \mathcal{N}(v) \right\rbra`
- `1810.00826` `eq:GIN-readout` (`method.tex:L89`): `\label{eq:GIN-readout} h_{G} = {\rm CONCAT} \Big( {\rm READOUT}\Big( \left\lbrace h_v^{(k)} | v \in G \right\r`
- `2007.02133` `eqn:GCNII_filter` (`appendix.tex:L30`): `\label{eqn:GCNII_filter} \mathbf{H}^{(K-1)} = \left(\sum_{\ell=0}^{K-1}\left(\prod_{k=K-\ell-1}^{K-1}\gamma_{k`
- `2007.02133` `eqn:filter` (`appendix.tex:L53`): `\label{eqn:filter} \left(\sum_{k=0}^{K-1} \theta_{k} \tilde{\mathbf{L}}^{k}\right) \mathbf{x} \hspace{-1mm}= \`
- `2007.02133` `eqn:theta` (`appendix.tex:L78`): `\label{eqn:theta} \gamma_{K-\ell-1} = \left. \sum_{k=\ell}^{K-1} \theta_{k} (-1)^\ell {k\choose \ell} \middle/`
- `2007.02133` `eq_10` (`appendix.tex:L121`): `\mathbf{h}^{(K)} &= \left({\mathbf{I}_n+\tilde{\mathbf{D}}^{-1 / 2} \tilde{\mathbf{A}} \tilde{\mathbf{D}}^{-1 `
- `2007.02133` `eq_11` (`appendix.tex:L141`): `\mathbf{h}^{(K)} &= \tilde{\mathbf{D}}^{-1 / 2} \left({ \mathbf{I}_n+ \tilde{\mathbf{A}} \tilde{\mathbf{D}}^{-`
- `2007.02133` `eq_13` (`appendix.tex:L177`): `\mathbf{h}^{(K)} = {\left<\tilde{\mathbf{D}}^{1 / 2} \mathbf{1}, \mathbf{x} \right> \over 2m+n} \tilde{\mathbf`
