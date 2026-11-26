# Incident Narrative Triage: Deterministic Summaries and LLM Step Status

**Status: partial.** The deterministic analysis is complete and reproducible. The Gemini (`gemini-1.5-pro`) triage step was **not executed**: no `GEMINI_API_KEY` or `GOOGLE_API_KEY` is set in the run environment, so `outputs/gemini_raw.json` does **not** exist and no LLM-generated labels, priorities, or pattern summaries are reported here.

## 1. Methods

### 1.1 Data
- Input: `data/incident_narratives.csv` (read-only), 6 rows, fields `incident_id`, `source_system`, `narrative_text`.
- Preprocessing (`code/analyze.py`): strip field whitespace, lowercase `source_system`, collapse internal whitespace in narratives, drop rows with missing id/narrative or with a `source_system` outside {`edr`, `network_ids`}. All 6 rows passed validation (0 rejected).

### 1.2 Quantitative summaries (all computed by `code/analyze.py`)
- **Counts by source_system.** Incidents per sensor family.
- **Narrative length.** Word count via regex tokens `[a-z0-9][a-z0-9_\-\.]*`, plus character count.
- **Keyword-group coverage.** Seven analyst-defined keyword groups (documented in `analyze.py`, `KEYWORD_GROUPS`), matched as lowercase substrings. The metric is the share of incidents per source with at least one hit. These groups are descriptive themes, not tactic labels.
- **Frequent terms.** Stopword-filtered unigram and bigram document frequencies per source (`out/tables/top_terms_*.csv`, `top_bigrams_*.csv`).

### 1.3 Figures
- `report/images/counts_by_source.png`: incidents by source_system.
- `report/images/keyword_groups_by_source.png`: keyword-group coverage by source_system.

### 1.4 LLM step (planned, not executed)
- `code/llm_triage.py` calls the Gemini `generateContent` endpoint with `model` fixed to `gemini-1.5-pro`, sends all narratives plus the computed summary tables, requests JSON output, and writes the verbatim response to `outputs/gemini_raw.json`.
- The prompt forbids invented IOCs and any quantitative claim not present in the summary tables.
- The script exits with status 2 and writes nothing when no key is present. This run hit that path (`out/llm_triage_stdout.log`).

## 2. Results

### 2.1 Counts by source_system (`out/tables/counts_by_source.csv`)

| source_system | n incidents |
|---|---|
| edr | 3 |
| network_ids | 3 |

### 2.2 Narrative length (`out/tables/length_by_source.csv`)

| source_system | n | words min | words mean | words max | chars mean |
|---|---|---|---|---|---|
| edr | 3 | 15 | 16.00 | 17 | 122.0 |
| network_ids | 3 | 18 | 18.33 | 19 | 120.3 |

Narrative length is nearly identical across sources, so length does not separate them.

### 2.3 Keyword-group coverage by source (`out/tables/keyword_group_by_source.csv`)

| keyword group | edr (hits/n) | network_ids (hits/n) |
|---|---|---|
| execution_script | 1/3 | 0/3 |
| credential_auth | 1/3 | 0/3 |
| network_traffic | 0/3 | 3/3 |
| file_data | 1/3 | 2/3 |
| containment_action | 2/3 | 3/3 |
| false_positive_closure | 1/3 | 1/3 |
| process_notification | 2/3 | 2/3 |

Descriptive only. With n = 3 per group, one incident moves a share by 0.33.

### 2.4 Pattern observations (from the tables and the raw text)
- The `network_traffic` keywords (DNS, SMB, TLS, subnet, outbound, connections) appear in all three `network_ids` narratives and in none of the `edr` narratives. This is a direct result of the wording in the data.
- Script- and credential-themed keywords (PowerShell/encoded, failed logins/admin account) appear only in `edr` narratives.
- Containment-style actions (blocked, disabled, sinkhole, challenge, reset) appear in most incidents of both sources.

### 2.5 Triage summary
Not available. The LLM triage (label set, per-incident tactic/priority, recurring patterns) was not run. No labels were assigned in this report.

## 3. Discussion
*Interpretation limited to the deterministic results above.*

- The source split is clean in keyword terms: `edr` narratives describe endpoint process and account events, and `network_ids` narratives describe traffic and network-level containment. This matches what each sensor family would be expected to see, but the sample is 3 + 3, so it is a description of these six rows and not evidence about either sensor in general.
- Keyword groups are coarse. For example, `false_positive_closure` matches on the substring "no " and so over-triggers. Its results should be treated as weak.
- Narrative length carries no discriminating signal.
- Once a `GEMINI_API_KEY` is provided, the pending step is to run `python3 code/llm_triage.py` and then add the triage section. Whether the model's labels agree with the keyword pattern above is an open question the data cannot answer at this sample size.

## 4. Limitations
- **LLM step not executed.** No `outputs/gemini_raw.json` exists. Any LLM-derived triage claim is absent, not estimated.
- **Very small N.** Six incidents, three per source. No statistical test is meaningful, and all contrasts are tentative.
- **Synthetic data.** The narratives come from a synthetic exercise, and the source_system label is a sensor-family tag, not a causal attribute.
- **Keyword lists are hand-built.** They were written from the six narratives, so they describe those narratives and are not validated against any larger corpus.
- **No IOC analysis.** The narratives contain some identifiers (e.g. hostnames, `explorer.exe`); these are not analyzed as indicators.

## 5. Reproduction
```
python3 code/analyze.py          # -> out/tables/*.csv, out/summary.json, report/images/*.png
GEMINI_API_KEY=... python3 code/llm_triage.py   # -> outputs/gemini_raw.json (requires key)
```
Captured logs: `out/analyze_stdout.log`, `out/llm_triage_stdout.log`.
