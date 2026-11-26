# Inventory Reconciliation Report: WMS Export A vs. WMS Export B

**Scope:** `data/wms_alpha.csv` (Export A, 2 rows) and `data/wms_beta.csv` (Export B, 1 row).
**Reproduce:** `python3 -I code/reconcile.py` (stdlib only). Full log: `out/run_log.txt`. Machine-readable outputs: `out/kpis.json`, `out/recon_detail.csv`, `out/sensitivity_offset.csv`.

## Bottom line

The two exports agree on the one record they share (SKU A-1, 10 units, 2026-03-01). Export A has one additional snapshot (2026-03-02, 10 units) with no counterpart in Export B. Both exports together contain only **one SKU and one warehouse on one matched day**, so these KPIs describe the data sample. They do not establish a reliable inventory accuracy rate. Management should treat them as a pipeline check, not as a performance result, until a full-period export is reconciled.

## Data

| File | Rows | Columns | Warehouse code | Timestamp |
|---|---|---|---|---|
| `wms_alpha.csv` (A) | 2 | `sku, qty, warehouse, as_of_utc` | `WH1` | `YYYY-MM-DD HH:MM:SS+00` (explicit UTC) |
| `wms_beta.csv` (B) | 1 | `SKU, Quantity, Site, timestamp_local` | `Warehouse-01` | `YYYY-MM-DD HH:MM:SS` (no offset, "local") |

No nulls, no duplicate keys, and no unparseable values in either file.

## Method

1. **Normalize keys.** SKUs are trimmed and upper-cased. Warehouse codes are mapped `WH1` ↔ `Warehouse-01` to a canonical `WH1`. This mapping is an **assumption**: each file contains only one warehouse, and the mapping is not documented in the data.
2. **Normalize time.** A timestamps are already UTC. B timestamps are treated as UTC+0 in the base case, because no offset is given. The B timezone is an **assumption** and is stress-tested below.
3. **Join grain.** Records are matched on `(SKU, warehouse, UTC calendar date)`. Quantities are point-in-time snapshots, so a daily snapshot comparison is the only defensible join.
4. **Classify each key** as `matched` (quantities compared), `only_in_A`, `only_in_B`, or `duplicate_key`.
5. **Compare quantities** on matched keys: `qty_diff = qty_A − qty_B`.

## Reconciliation results (base case: B local = UTC+0)

| Key (SKU, WH, UTC date) | Qty A | Qty B | Diff (A−B) | Status |
|---|---:|---:|---:|---|
| A-1, WH1, 2026-03-01 | 10 | 10 | 0 | matched, quantities agree |
| A-1, WH1, 2026-03-02 | 10 | — | — | only in A (no B record) |

## KPIs

| KPI | Value | Notes |
|---|---:|---|
| Rows in A / B | 2 / 1 | |
| Keys total (union) | 2 | |
| Matched keys | 1 | |
| Match rate of A keys | **50.0%** (1 of 2) | Driven by a single unmatched snapshot. |
| Coverage of B keys | **100.0%** (1 of 1) | Every B record found a counterpart in A. |
| Only in A | 1 | A-1/WH1/2026-03-02, 10 units |
| Only in B | 0 | |
| Quantity accuracy on matched keys | **100.0%** (0 of 1 mismatched) | n = 1, so this carries no statistical weight. |
| Units matched (A / B) | 10 / 10 | |
| Units present only in A | 10 | |

## Sensitivity to the B timezone assumption

B's "local" time has no offset, so I tested every offset from UTC-12 to UTC+14 (`out/sensitivity_offset.csv`).

- **UTC-12 through UTC+8:** the B record falls on 2026-03-01 (UTC), the match holds, and the result above is unchanged.
- **UTC+9 and higher:** the B timestamp rolls back to 2026-02-28 (UTC). The record no longer matches A, and the result becomes 0 matched keys, 2 only-in-A, and 1 only-in-B. Every KPI above would change.

The result therefore depends on B's timezone being at or west of UTC+8. The export should carry an explicit offset (or be stated as UTC) before any KPI is published.

## Data-quality findings

1. **Inconsistent warehouse identifiers** (`WH1` vs. `Warehouse-01`). A mapping table is needed; the current one is inferred.
2. **Inconsistent column names and conventions:** lower-case vs. upper-case headers, `qty` vs. `Quantity`, and `as_of_utc` (explicit UTC) vs. `timestamp_local` (no offset).
3. **Quantity formats differ:** `10` (integer) in A, `10.0` (float) in B. Both were parsed as numbers without loss.
4. **Snapshot cadence is undocumented.** A has daily snapshots, and B has a single snapshot. It is unclear whether B exports are sampled or whether B is missing days.
5. **Sample size is too small** for any rate to be meaningful: one SKU, one warehouse, one matched key.

## Limitations

- Two A rows and one B row cannot support inferences about the population. The 50% match rate and the 100% quantity accuracy are descriptive of this sample only.
- Summing snapshot quantities across dates (e.g., "units only in A = 10") is not a stock position. Snapshots must not be added across time.
- The WH1 ↔ Warehouse-01 mapping and the B timezone are assumptions. The sensitivity analysis shows that the timezone assumption can change the result.

## Recommendations

1. **Obtain full-period exports** from both WMSs covering the same SKUs, warehouses, and date range. Reconcile on that basis before publishing KPIs.
2. **Standardize the export contract:** a single warehouse identifier (with a documented mapping), explicit UTC timestamps, and consistent column names and numeric types.
3. **Confirm the B timezone** and the warehouse mapping with the owner of Export B.
4. **Investigate the unmatched A snapshot** (A-1, WH1, 2026-03-02) once B data for that date is available. Determine whether it is a timing gap or a missing record.
5. **Re-run `code/reconcile.py`** on the full data. The script is generic over rows, and its keying, match status, and sensitivity logic will apply without modification, provided the input schema is the same.

## Deliverables

- `report/report.md` (this file), also copied to `report/inventory_recon_report.md` to match the requested filename.
- `code/reconcile.py`: reconciliation, KPI, and sensitivity logic.
- `out/`: run log, KPI JSON, per-key detail, and timezone sensitivity table.
