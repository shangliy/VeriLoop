"""Step 3: figures generated only from outputs/ artifacts written by code/preprocess_and_summarize.py.

Output: report/images/theme_prevalence_by_cohort.png
        report/images/response_length_by_cohort.png
"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "outputs")
IMG = os.path.join(ROOT, "report", "images")
os.makedirs(IMG, exist_ok=True)

with open(os.path.join(OUT, "descriptives.json"), encoding="utf-8") as f:
    desc = json.load(f)
proc = pd.read_csv(os.path.join(OUT, "processed_responses.csv"))

COHORTS = ["transit_primary", "car_primary"]
COLORS = {"transit_primary": "#1f77b4", "car_primary": "#d62728"}

# --- Figure 1: theme prevalence (proportion of respondents in cohort) ---
themes = list(desc["theme_by_cohort"].keys())
props = {c: [desc["theme_by_cohort"][t][c]["prop"] for t in themes] for c in COHORTS}
pvals = {t: desc["theme_by_cohort"][t].get("fisher_p_two_sided") for t in themes}

fig, ax = plt.subplots(figsize=(10, 5.5))
y = range(len(themes))
h = 0.38
for i, c in enumerate(COHORTS):
    ax.barh([v + (i - 0.5) * h for v in y], props[c], height=h, color=COLORS[c],
            label=f"{c} (n={desc['cohort_counts'][c]})")
ax.set_yticks(list(y))
ax.set_yticklabels([t.replace("_", " ") for t in themes])
ax.invert_yaxis()
ax.set_xlim(0, 1)
ax.set_xlabel("Share of respondents in cohort with theme keyword present")
ax.set_title("Keyword-codebook theme prevalence by cohort (a-priori codebook, scripted)")
ax.legend(loc="lower right", fontsize=9)
fig.text(0.01, 0.01,
         "Fisher exact p (two-sided, uncorrected, exploratory): " +
         "; ".join(f"{t}={p}" for t, p in pvals.items() if p is not None and p < 0.1) +
         " (none < 0.05)",
         fontsize=7.5, wrap=True)
fig.tight_layout(rect=(0, 0.04, 1, 1))
p1 = os.path.join(IMG, "theme_prevalence_by_cohort.png")
fig.savefig(p1, dpi=150)
plt.close(fig)
print(f"wrote {os.path.relpath(p1, ROOT)}")

# --- Figure 2: response length (words) by cohort ---
fig, ax = plt.subplots(figsize=(6.5, 4.5))
data = [proc.loc[proc["cohort"] == c, "n_words"].values for c in COHORTS]
bp = ax.boxplot(data, tick_labels=COHORTS, widths=0.5, patch_artist=True)
for patch, c in zip(bp["boxes"], COHORTS):
    patch.set_facecolor(COLORS[c])
    patch.set_alpha(0.35)
for i, (vals, c) in enumerate(zip(data, COHORTS), start=1):
    ax.scatter([i] * len(vals), vals, color=COLORS[c], zorder=3, s=18)
ax.set_ylabel("Words per response (alphabetic tokens)")
ax.set_title("Response length by cohort (each point = one respondent)")
fig.tight_layout()
p2 = os.path.join(IMG, "response_length_by_cohort.png")
fig.savefig(p2, dpi=150)
plt.close(fig)
print(f"wrote {os.path.relpath(p2, ROOT)}")
