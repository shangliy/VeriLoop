# Monthly advertising budget analysis

## Decision and policy

Use the rolling rule **store budget in month m = the authorized fixed share × that store’s actual sales in month m−1**. Apply it separately to each store, then sum the store budgets. Year 4 January can be set from observed year 3 December sales; refresh February–December as each preceding month closes. A full-year schedule is useful for cash planning, but its later months are forecasts, not final policy budgets.

The data do not specify the authorized share, and observed spending is inconsistent with a single fixed lagged-sales share. For illustration only, the tables below use **2.7591519%**, the ratio of total observed spending to total prior-month sales across all available store-month pairs. This is a historical aggregate calibration, not evidence of the policy rate or an optimal advertising rate. Replace it with the authorized share (or the applicable store-specific share) before implementation. At a different common share, multiply every scenario amount by `authorized share / 0.02759151868407384`.

## Year 4 portfolio planning scenario

| Budget month | Prior-month sales basis ($m) | Illustrative ad budget ($m) |
|---|---:|---:|
| 1 | 102.300 | 2.823 |
| 2 | 102.640 | 2.832 |
| 3 | 45.668 | 1.260 |
| 4 | 45.898 | 1.266 |
| 5 | 45.936 | 1.267 |
| 6 | 45.651 | 1.260 |
| 7 | 45.731 | 1.262 |
| 8 | 46.044 | 1.270 |
| 9 | 45.959 | 1.268 |
| 10 | 46.321 | 1.278 |
| 11 | 46.063 | 1.271 |
| 12 | 102.376 | 2.825 |
| **Total** | **720.591** | **19.882** |

January uses actual year 3 December sales. For each later month, the forecast of year 4 prior-month sales equals that store’s sales in the same month of year 3; for example, the February budget uses a forecast of year 4 January sales based on year 3 January. This preserves the one-month policy lag, including across the year boundary. Amounts are rounded for display; the portfolio sums cent-rounded store budgets. The corresponding store-level schedule is in `out/store_month_budget_scenario.csv`; portfolio amounts and unrounded share are in `out/monthly_budget_scenario.csv`. The schedule assumes the same 200 stores remain active and makes no allowance for new stores, closures, or changes in the business environment.

## Evidence and validation

The dataset has 7,200 records: 200 stores for each of 36 months, with no missing fields, duplicate store-month keys, or gaps in the balanced panel. Years are coded 1–3 rather than calendar years. Observed year 3 advertising totaled $20.204 million, compared with the $19.882 million scenario; the difference is descriptive and does not establish savings or a comparable expected outcome.

Across 7,000 valid consecutive-month pairs, the median ratio of ad spend to prior sales was 2.287%, with the 10th–90th percentile spanning 1.193%–4.069%. The median absolute deviation from the fitted common-share budget was 30.6% of that fitted budget. Monthly median ratios ranged from 0.94% in February to 8.19% in November. Thus historical spending does not consistently implement the stated fixed-share rule; a pooled historical ratio cannot establish either a common or store-specific authorized share. Holiday flags occur in January, November, and December in every year; timing makes the lag consequential: for example, November’s scenario is based on October sales, not November holiday sales.

A single historical holdout checks the seasonal-naive sales basis: forecast each prior month of year 3 using the same store and month of year 2, then compare it with actual year 3 sales. For budget months 2–12, portfolio forecast errors ranged from −1.13% to +0.44%; store-level weighted absolute percentage errors ranged from 3.81% to 9.98%. January is based on already observed December and is not a forecast test. These are descriptive results from one year, not prediction intervals or guarantees; common shocks, trend changes, and store-level errors can make future deviations larger. Roll forward actual sales monthly and monitor the forecast versus realized budget requirement.

Ad spend and same-month sales correlate 0.993 across valid lag pairs, but this is not a causal return on advertising. Seasonality, common demand shocks, and budget selection can affect both; contemporaneous foot traffic may also respond to advertising and is not an independently established pre-treatment control. The panel and policy timing do not identify incremental ad revenue, profitability, or an optimal spend share. A randomized store-level budget test, where authorized and feasible, with predefined outcomes and measurement of sales and margin, would be needed to evaluate incremental returns.

## Reproduction

From the workspace root, run `python code/analysis.py > out/analysis_stdout.txt`. The script validates panel keys and completeness, computes lagged ratios and the holdout, and writes the two scenario CSVs. Its raw output is `out/analysis_stdout.txt`.
