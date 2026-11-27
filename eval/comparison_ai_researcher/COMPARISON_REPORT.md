# VeriLoop v5 vs. HKUDS/AI-Researcher — Reproducible Automated Audit Comparison

- **Generated (UTC):** `2026-11-27T07:30:47Z`
- **Methodology:** Identical zero-override deterministic Layer-1 auditors (`pdf_audit.py` / `trace_numbers.py`, `audit_code.py --strict`, `citation_audit.py`) executed directly on VeriLoop v5 multi-domain RTX 3060 Ti workspaces and official published `HKUDS/AI-Researcher/examples/*` showcase outputs (`paper.pdf` + `project/`). Layer-1 audit cost: `$0.00`.
- **Fairness Note:** Official `HKUDS/AI-Researcher/examples/*` repositories publish `paper.pdf` + `project/` codebases, and only a subset include raw `.log` files (`workspaces_with_logs`). Both overall trace rate and **with-logs-only** trace rate are reported explicitly below.

## 1. System-Level Aggregate Comparison

| System | Workspaces (With Logs) | Numbers Traced (All) | Numbers Traced (With Logs Only) | AST Clean Workspaces (0 HIGH) | Total AST HIGH / MED | Verified BibTeX Coverage | Governance Score (Claims/Bind/Gate/UI) | Mean Audit Latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **VeriLoop v5** | `3` (`3`) | `683/683` (**100.0%**) | **100.0%** | **100.0%** | `0` / `0` | **100.0%** | **100.0%** | `233 ms` |
| **HKUDS/AI-Researcher** | `7` (`7`) | `133/184` (**72.3%**) | **72.3%** | **100.0%** | `0` / `0` | **0.0%** | **0.0%** | `302 ms` |

## 2. Per-Workspace Forensic Breakdown

| System | Workspace | Domain | Deliverable | Logs | Traced / Total | AST HIGH (Codes) | AST MED | Citation Mode | Claims / Bind / UI |
|---|---|---|---|---:|---:|---|---:|---|---|
| VeriLoop v5 | `VeriLoop-v5 (CV: CIFAR-10 & F-MNIST, 42 GPU runs)` | CV | `pdf` | `8` | `195/195` (100.0%) | `0` (—) | `0` | `bibtex_online_committed` | ✅ / ✅ / ✅ |
| VeriLoop v5 | `VeriLoop-v5 (GNN: Cora & CiteSeer, 50 GPU runs)` | GNN | `text` | `10` | `281/281` (100.0%) | `0` (—) | `0` | `bibtex_local` | ✅ / ✅ / ✅ |
| VeriLoop v5 | `VeriLoop-v5 (RecSys: MovieLens-100K, 10 GPU runs)` | RecSys | `text` | `6` | `207/207` (100.0%) | `0` (—) | `0` | `bibtex_local` | ✅ / ✅ / ✅ |
| HKUDS/AI-Researcher | `AI-Researcher (con_flowmatching)` | Diffusion/Flow | `pdf` | `6` | `0/7` (0.0%) | `0` (—) | `0` | `pdf_only_no_bib` | ❌ / ❌ / ❌ |
| HKUDS/AI-Researcher | `AI-Researcher (dccf)` | RecSys | `pdf` | `13` | `35/57` (61.4%) | `0` (—) | `0` | `pdf_only_no_bib` | ❌ / ❌ / ❌ |
| HKUDS/AI-Researcher | `AI-Researcher (fsq)` | VQ/CV | `pdf` | `8` | `0/0` (100.0%) | `0` (—) | `0` | `pdf_only_no_bib` | ❌ / ❌ / ❌ |
| HKUDS/AI-Researcher | `AI-Researcher (gnn_difformer)` | GNN | `pdf` | `18` | `32/32` (100.0%) | `0` (—) | `0` | `pdf_only_no_bib` | ❌ / ❌ / ❌ |
| HKUDS/AI-Researcher | `AI-Researcher (gnn_nodeformer)` | GNN | `pdf` | `12` | `0/0` (100.0%) | `0` (—) | `0` | `pdf_only_no_bib` | ❌ / ❌ / ❌ |
| HKUDS/AI-Researcher | `AI-Researcher (hgcl)` | RecSys | `pdf` | `6` | `43/43` (100.0%) | `0` (—) | `0` | `pdf_only_no_bib` | ❌ / ❌ / ❌ |
| HKUDS/AI-Researcher | `AI-Researcher (rotation_vq)` | VQ/CV | `pdf` | `2` | `23/45` (51.1%) | `0` (—) | `0` | `pdf_only_no_bib` | ❌ / ❌ / ❌ |
