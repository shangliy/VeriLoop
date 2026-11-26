# Interview Thematic Analysis: Transit-primary vs Car-primary Respondents

**STATUS: INFEASIBLE (partial).** The LLM-assisted thematic analysis (Step 2, Anthropic Messages API, `claude-3-5-sonnet-20241022`) could not be performed because no `ANTHROPIC_API_KEY` is available in this environment. The raw evidence is in `out/llm_thematic_analysis.txt`. No `outputs/anthropic_messages_response.json` was written, and no LLM output was fabricated or substituted. Steps 1 (scripted preprocessing and descriptives) and 3 (figures) are complete and fully traceable. The thematic findings below come only from the scripted codebook, not from an LLM.

## 1. Methods

### 1.1 Data
- Input: `data/interview_excerpts.csv` (read-only), 18 rows, columns `respondent_id`, `cohort`, `response_text`.
- SHA-256 of input: `7022c685aec577bc532c4f792dd8e2ed8ce2b5b39ce4d13ee7bcb05354c78af3` (logged in `out/preprocess_and_summarize.txt`).
- Validation (scripted): unique IDs, only the two expected cohort labels, no empty responses. All checks passed.

### 1.2 Preprocessing (`code/preprocess_and_summarize.py`)
- Deterministic normalization: em/en dashes and curly apostrophes mapped to ASCII; whitespace collapsed.
- Word count = alphabetic tokens (`[A-Za-z][A-Za-z'\-]*`); character count; sentence count (`[.!?]` followed by whitespace or end).

### 1.3 A-priori keyword codebook
Ten themes were fixed in code before any counts were inspected. A theme is "present" in a response when at least one regex matches the lower-cased normalized text. The full pattern list is stored in `outputs/descriptives.json` under `codebook`. The matched surface forms are logged per theme, so every count can be checked by hand.

Caveat: several themes were written with vocabulary that naturally recurs in one cohort (for example `driving_parking`). This is discussed in Section 4.

### 1.4 Statistics
- Counts and proportions per cohort (n = 9 per cohort).
- Two-sided Fisher exact test per theme (cohort × theme presence), via scipy. p-values are **uncorrected** and exploratory.

### 1.5 Figures (`code/make_figures.py`)
- `report/images/theme_prevalence_by_cohort.png`: theme prevalence by cohort.
- `report/images/response_length_by_cohort.png`: response length (words) by cohort, one point per respondent.

### 1.6 LLM step (`code/llm_thematic_analysis.py`)
The script builds a prompt containing all excerpts and the scripted counts, then calls `claude-3-5-sonnet-20241022` with `temperature=0` and `max_tokens=2000`. It writes the full response only on success. On this run it recorded `STATUS: BLOCKED - no ANTHROPIC_API_KEY in environment; no API call attempted.` The script has not been exercised against the live API, so its API path is untested.

### 1.7 Environment
Python 3.12 (anaconda), pandas 3.0.3, numpy 2.4.6, matplotlib 3.10.9, scipy 1.17.1. Running the scripts printed NumPy 1.x/2.x binary-compatibility warnings from the numexpr and bottleneck extensions. These are non-fatal. Both scripts exited 0 and produced their outputs.

## 2. Results (from code)

### 2.1 Cohort counts and response length
Source: `out/preprocess_and_summarize.txt`, `outputs/descriptives.json`.

| Cohort | n | Words mean | Words median | Words min–max | Themes per response (mean) |
|---|---|---|---|---|---|
| transit_primary | 9 | 20.56 | 20 | 16–27 | 1.44 |
| car_primary | 9 | 19.78 | 19 | 16–24 | 2.22 |

Response length is nearly identical across cohorts (`response_length_by_cohort.png`). Car-cohort responses hit more codebook themes on average, but this is partly a function of the codebook (see Section 4).

### 2.2 Theme frequencies by cohort
Source: `outputs/descriptives.json` (`theme_by_cohort`). Each cell is the number of respondents, out of 9, whose response matches the theme. p = two-sided Fisher exact, uncorrected.

| Theme | transit (n/9) | car (n/9) | overall (n/18) | Fisher p |
|---|---|---|---|---|
| real_time_reliability | 3 | 3 | 6 | 1.000 |
| crowding_safety | 2 | 2 | 4 | 1.000 |
| pricing_cost | 1 | 3 | 4 | 0.577 |
| accessibility | 1 | 0 | 1 | 1.000 |
| navigation_transfers | 2 | 2 | 4 | 1.000 |
| connectivity_offline | 1 | 0 | 1 | 1.000 |
| trust_communication | 2 | 3 | 5 | 1.000 |
| driving_parking | 0 | 4 | 4 | 0.082 |
| interface_simplicity | 0 | 1 | 1 | 1.000 |
| multimodal_integration | 1 | 2 | 3 | 1.000 |

![Theme prevalence by cohort](images/theme_prevalence_by_cohort.png)

No theme reaches p < 0.05. The smallest p-value is `driving_parking` at 0.082, and the count is 0 vs 4 of 9.

### 2.3 Matched surface forms (audit)
From `out/preprocess_and_summarize.txt`. For example, `driving_parking` matched `drive` (2), `parking` (2), `driving` (1), `lot` (1), `traffic` (1). `real_time_reliability` matched the words `wrong` and `eta` among others. Every theme's matches are listed in full in the log.

## 3. Discussion

The scripted descriptives show a clear shape, although the sample is very small:

- **Shared concern: reliability and trust in information.** `real_time_reliability` appears equally in both cohorts (3/9 each), and `trust_communication` is nearly balanced (2/9 transit, 3/9 car). The excerpts reflect this. The transit respondent INT-01 describes a wrong live arrival board causing missed connections, and the car respondent INT-18 says "if the line on the map is wrong I assume the whole trip plan is wrong." Both point to dependence on the app's information being correct.
- **Transit-cohort emphasis: transfers, offline use, and accessibility.** Transit-cohort responses mention accessibility (1), offline or signal loss (1), and transfer and station navigation (2). The car cohort has none of the accessibility or offline themes.
- **Car-cohort emphasis: driving, parking, and cost.** Four of nine car-cohort responses concern driving or parking, and three concern pricing or fuel. Driving and parking are absent from the transit cohort. This is the most pronounced contrast, with p = 0.082, but it is exploratory, uncorrected, and partly constructed by the codebook.
- **Cross-cohort integration.** Multimodal themes (bike docks, park-and-ride, carpool) appear in both cohorts (1 transit, 2 car). The car-cohort responses are the ones asking for integrated trip planning across driving and train legs.

These patterns are descriptive. They do not establish that the cohorts differ on any theme. The one nominal difference is a 0-vs-4 comparison within groups of nine.

**What the LLM step would add.** The planned step was to use the LLM to produce inductive themes with respondent-level support and cross-cohort contrasts, anchored to these counts. None of that has been done. The themes above are keyword-based and will miss paraphrases, negations, and meaning that does not appear as a keyword. Any inductive-theme claim beyond the codebook is therefore unsupported in this report.

## 4. Limitations

1. **LLM step not performed (blocking).** Step 2 requires the Anthropic Messages API. No API key is set in this environment, and the run log records `BLOCKED`. Thematic coding by an LLM is absent from this report, and the report is `STATUS: INFEASIBLE` for that reason.
2. **Very small sample.** 18 respondents (9 per cohort). Fisher p-values have very low power and cannot support a generalization.
3. **Keyword codebook, not validated coding.** Themes are matched by regex. This misses paraphrase and negation and can produce false positives (for example, `caps` could match non-pricing uses, and `lot` could match "a lot"). No inter-coder reliability was assessed.
4. **Codebook is not cohort-neutral.** Some themes use vocabulary that is near-definitional for one cohort, such as driving, parking, and traffic in `driving_parking`. The car-vs-transit contrast on that theme is partly built in, so it should not be read as an independent finding.
5. **Multiple comparisons.** Ten themes were tested with no correction. Under a Bonferroni correction for ten tests, no result would be significant.
6. **Descriptive length metrics.** Word counts are alphabetic-token counts, which is a crude proxy for response richness.
7. **Unverified API code path.** `code/llm_thematic_analysis.py` has not been run against the live API. Its failure path was exercised, its success path was not, and the model ID `claude-3-5-sonnet-20241022` was not checked for availability.
8. **Excerpts only.** The data are short excerpts, not full transcripts, so context and follow-up are unavailable.

## 5. Reproducibility

Run from the workspace root, using the anaconda Python:

```
/home/shawnyang/anaconda3/bin/python -I code/preprocess_and_summarize.py > out/preprocess_and_summarize.txt 2>&1
/home/shawnyang/anaconda3/bin/python -I code/make_figures.py > out/make_figures.txt 2>&1
/home/shawnyang/anaconda3/bin/python -I code/llm_thematic_analysis.py > out/llm_thematic_analysis.txt 2>&1
```

Artifacts:
- `outputs/processed_responses.csv`: normalized text, counts, and theme flags per respondent.
- `outputs/descriptives.json`: all summary numbers quoted in this report.
- `out/*.txt`: stdout logs for each script.
- `report/images/*.png`: figures.

To complete Step 2, set `ANTHROPIC_API_KEY` and rerun `code/llm_thematic_analysis.py`. On success it writes `outputs/anthropic_messages_response.json`. This report should then be updated with LLM-derived themes, citing that file.
