# VeriLoop Level-2 Research Plan

- **Generated (UTC):** `2026-11-27T07:17:06Z`
- **Mode:** `Level-2` (Reference-Driven Gap & Innovation)
- **Primary Hypothesis (`C1_Primary`):** Targeted algorithmic refinement addressing calibration, generalization, and reproducibility gaps across reference methods across reference study (LightGCN: Simplifying and Powering Graph Convolution Network for Recommendation; Are Graph Augmentations Necessary? Simple Graph Contrastive Learning for Recommendation) improves held-out evaluation metrics over the baseline under strict validation-only selection.
- **Kill Criterion:** Refined method fails to outperform the baseline across planned seeds or violates VeriLoop AST/provenance gates.
- **Ingested References:** `2` papers, `26` formula↔code alignments, `0` unmatched equations

## Mandatory VeriLoop Governance Contracts
1. Strict validation-only model & hyperparameter selection (zero test-split tuning).
2. All reported tables & macros auto-bound from raw TensorBoard/W&B/CSV logs via `./veriloop bind`.
3. Every citation verified against arXiv/Crossref/Semantic Scholar (`./veriloop verify-cites`).
4. Hard blocking gate (`./veriloop gate`, exit code `2`) must pass before delivery.
