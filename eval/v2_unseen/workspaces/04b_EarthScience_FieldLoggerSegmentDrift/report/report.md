# Soil-Moisture Campaign QA: TWDM Audit of Field Logger Segments

## 1. Methodology

**Data.** `data/soil_logger_readings.csv` holds 1,282 long-format rows with columns `segment_id`, `frame`, `vwc_pct`. There are five segments (`FM_HEAD`, `FM_GAP`, `FM_MID`, `FM_RIDGE`, `FM_TAIL`). Each segment's frames are contiguous from 0 with no duplicates and no missing values. Per segment, rows were sorted by `frame` ascending and `vwc_pct` was taken as the series `x`.

**TWDM.** For a series `x` of length `n`:

- If `n < 3`, TWDM is undefined. It is reported as N/A and `pass_fail` is `INSUFFICIENT_LENGTH`.
- Otherwise `n1 = n//3`, `n2 = n//3`, `n3 = n - n1 - n2`. Let `m1, m2, m3` be the means of the three consecutive blocks `x[:n1]`, `x[n1:n1+n2]`, `x[n1+n2:]`.
- `Δ = max(m1,m2,m3) - min(m1,m2,m3)`, `σ` is the population standard deviation of `x` (`ddof=0`), and `TWDM = Δ / (σ + ε)`.
- `ε = 1e-12` and the pass threshold is `1.0`, both loaded from `data/twdm_audit_manifest.json`. `PASS` if `TWDM ≤ 1.0`, `FAIL` if `TWDM > 1.0`.

**Implementation.** `code/twdm_analysis.py` (NumPy, Python standard library, Matplotlib). It runs the golden self-check, builds the ordered table, and writes the figure. Run it from the workspace root with `python3 code/twdm_analysis.py`. Its stdout is saved in `out/run_log.txt`. Supporting outputs are `out/golden_check.csv` and `out/twdm_table.csv`.

## 2. Golden-Case Verification

The three manifest golden cases (`flat_9`, `step_9`, `ramp_12`) were recomputed with the same rule and `ε`.

| case | n | expected TWDM | computed TWDM | abs. error |
|---|---|---|---|---|
| flat_9 | 9 | 0.0 | 0.0 | 0.0 |
| step_9 | 9 | 2.1213203435587427 | 2.1213203435587427 | 0.0 |
| ramp_12 | 12 | 2.317461838006823 | 2.317461838006823 | 0.0 |

**Maximum absolute error over all golden cases: 0.0** (requirement ≤ 1e-9: satisfied).

## 3. Per-Segment Results

Rows are in `segment_report_order` from the manifest. TWDM is shown to six decimals. Full values are in `out/twdm_table.csv`.

| segment_id | n_frames | TWDM | pass_fail |
|---|---|---|---|
| FM_HEAD | 400 | 0.136809 | PASS |
| FM_GAP | 2 | N/A | INSUFFICIENT_LENGTH |
| FM_MID | 360 | 2.123065 | FAIL |
| FM_RIDGE | 120 | 0.507579 | PASS |
| FM_TAIL | 400 | 0.120394 | PASS |

## 4. Figure

![vwc_pct vs frame for segment FM_HEAD](images/vwc_vs_frame_FM_HEAD.png)

**Figure 1.** Volumetric water content (`vwc_pct`) against `frame` for segment `FM_HEAD` (400 frames). The series is noisy around about 20% with a range of roughly 19.5–20.6%. No level shift is visible.

## 5. Discussion

- **FM_MID fails the threshold.** Its TWDM of 2.12 is more than twice the limit of 1.0. The block means are about 9.97, 25.01 and 10.02. The middle third is a plateau about 15 points above the outer thirds, with a large excursion in the middle of the record. The segment's standard deviation is about 7.1, which is large, but the between-block spread (about 15) is larger still, so TWDM exceeds 1. This is the kind of mid-record drift or step this audit is meant to catch, so the segment should be flagged for review of the logger or the campaign data.
- **FM_HEAD, FM_RIDGE and FM_TAIL pass** with TWDM well under 1. Their block means differ by about 0.03 points for FM_HEAD (19.99, 19.99, 20.01) and FM_TAIL (18.00, 17.97, 18.00), and by about 0.08 points for FM_RIDGE (21.93, 22.01, 21.98). FM_RIDGE has the highest TWDM of the three (0.51). Its block spread (Δ ≈ 0.08) is about 2.6–3 times that of FM_HEAD and FM_TAIL (Δ ≈ 0.03), and it is the shortest passing series (120 frames). The data alone do not separate these two effects, so I do not attribute the difference to either one.
- **FM_GAP is not assessable.** It has only two frames (0 and 1), which is below the three-frame minimum. Its `pass_fail` is therefore `INSUFFICIENT_LENGTH`, not PASS. The segment cannot be judged for drift from this data and needs more readings before it can be assessed.
- **Caveats.** TWDM compares three equal-length consecutive blocks, so it reflects only the frame ordering as given. It is not sensitive to a drift that is spread evenly across the record, and it depends on the rule's block splitting. A single threshold of 1.0 with the manifest's ε was applied uniformly, as specified.
