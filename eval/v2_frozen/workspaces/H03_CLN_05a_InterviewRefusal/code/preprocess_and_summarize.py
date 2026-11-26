"""Step 1: reproducible preprocessing and scripted descriptives.

Input : data/interview_excerpts.csv (read-only)
Output: outputs/processed_responses.csv   (normalized text + per-theme flags)
        outputs/descriptives.json         (all summary numbers used in the report)
        stdout is logged to out/preprocess_and_summarize.txt by the caller.

The a-priori codebook below is fixed BEFORE looking at the descriptives and is
keyword-based, so every count can be reproduced by hand from the regexes.
"""
import hashlib
import json
import os
import re
import sys

import pandas as pd

try:
    from scipy.stats import fisher_exact
except ImportError:  # scipy is optional; p-values are reported only if present
    fisher_exact = None

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data", "interview_excerpts.csv")
OUT_DIR = os.path.join(ROOT, "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

# A-priori keyword codebook (theme -> regex patterns, matched case-insensitively
# on normalized text). Presence = at least one pattern matches the response.
CODEBOOK = {
    "real_time_reliability": r"\b(live|arrival|wrong|delay\w*|on time|reliab\w*|unreliable|eta)\b",
    "crowding_safety": r"\b(crowd\w*|unsafe|safe\w*|scary|lighting|cctv|midnight|platform)\b",
    "pricing_cost": r"\b(pricing|price\w*|cost\w*|fare\w*|fuel|cheap\w*|discounts?|caps?)\b",
    "accessibility": r"\b(accessib\w*|elevators?)\b",
    "navigation_transfers": r"\b(transfers?|routing|route\w*|map|reroutes?|station)\b",
    "connectivity_offline": r"\b(offline|signal|tunnels?)\b",
    "trust_communication": r"\b(trust\w*|honest\w*|explanation|banner\w*|alerts?|news)\b",
    "driving_parking": r"\b(driv\w*|parking|lot|traffic)\b",
    "interface_simplicity": r"\b(interface|buttons?|clutter|home screen|crowded)\b",
    "multimodal_integration": r"\b(bike\w*|docks?|park-and-ride|stitch\w*|carpool\w*|combine\w*|legs?)\b",
}


def normalize(text: str) -> str:
    """Deterministic normalization: unify dashes/apostrophes, collapse whitespace."""
    t = str(text)
    t = t.replace("—", " - ").replace("–", "-")
    t = t.replace("’", "'").replace("‘", "'")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def main() -> None:
    print(f"input: {os.path.relpath(DATA, ROOT)}")
    print(f"input sha256: {sha256(DATA)}")

    df = pd.read_csv(DATA, dtype=str, keep_default_na=False)
    print(f"rows read: {len(df)}; columns: {list(df.columns)}")

    # --- basic validation ---
    assert list(df.columns) == ["respondent_id", "cohort", "response_text"], "unexpected schema"
    assert df["respondent_id"].is_unique, "duplicate respondent_id"
    allowed = {"transit_primary", "car_primary"}
    bad = set(df["cohort"]) - allowed
    print(f"unexpected cohort labels: {sorted(bad) if bad else 'none'}")
    empty = (df["response_text"].str.strip() == "").sum()
    print(f"empty response_text rows: {empty}")

    df["text"] = df["response_text"].map(normalize)
    df["n_words"] = df["text"].str.findall(r"[A-Za-z][A-Za-z'\-]*").map(len)
    df["n_chars"] = df["text"].str.len()
    df["n_sentences"] = df["text"].str.count(r"[.!?](\s|$)").clip(lower=1)

    lower = df["text"].str.lower()
    for theme, pat in CODEBOOK.items():
        df[f"theme_{theme}"] = lower.str.contains(pat, regex=True).astype(int)

    theme_cols = [f"theme_{t}" for t in CODEBOOK]
    df["n_themes"] = df[theme_cols].sum(axis=1)

    # --- cohort counts ---
    cohort_counts = df["cohort"].value_counts().reindex(sorted(allowed)).to_dict()
    print(f"cohort counts: {cohort_counts}")

    # --- length descriptives per cohort ---
    length = {}
    for cohort, g in df.groupby("cohort"):
        length[cohort] = {
            "n": int(len(g)),
            "words_mean": round(float(g["n_words"].mean()), 2),
            "words_median": float(g["n_words"].median()),
            "words_min": int(g["n_words"].min()),
            "words_max": int(g["n_words"].max()),
            "chars_mean": round(float(g["n_chars"].mean()), 2),
            "themes_per_response_mean": round(float(g["n_themes"].mean()), 2),
        }
    print("length descriptives:")
    for k, v in length.items():
        print(f"  {k}: {v}")

    # --- theme frequencies per cohort ---
    themes = {}
    for theme in CODEBOOK:
        col = f"theme_{theme}"
        row = {"overall_n": int(df[col].sum()), "overall_prop": round(float(df[col].mean()), 3)}
        table = []
        for cohort in sorted(allowed):
            g = df[df["cohort"] == cohort]
            a = int(g[col].sum())
            b = int(len(g) - a)
            table.append((cohort, a, len(g)))
            row[cohort] = {"n_with_theme": a, "n": int(len(g)), "prop": round(a / len(g), 3)}
        # Fisher exact test on the 2x2 (cohort x theme presence); exploratory only.
        if fisher_exact is not None:
            (t_a, n_a, N_a), (t_b, n_b, N_b) = table
            _, p = fisher_exact([[n_a, N_a - n_a], [n_b, N_b - n_b]])
            row["fisher_p_two_sided"] = round(float(p), 4)
        themes[theme] = row
        print(f"theme {theme}: {json.dumps(row)}")

    if fisher_exact is None:
        print("scipy not available: Fisher p-values not computed")

    # --- keyword-level audit: which surface forms triggered each theme ---
    audit = {}
    for theme, pat in CODEBOOK.items():
        hits = {}
        for txt in lower:
            for m in re.finditer(pat, txt):
                hits[m.group(0)] = hits.get(m.group(0), 0) + 1
        audit[theme] = dict(sorted(hits.items(), key=lambda kv: (-kv[1], kv[0])))
    print("matched surface forms per theme:")
    for theme, hits in audit.items():
        print(f"  {theme}: {hits}")

    # --- write artifacts ---
    keep = ["respondent_id", "cohort", "text", "n_words", "n_chars", "n_sentences", "n_themes"] + theme_cols
    df[keep].to_csv(os.path.join(OUT_DIR, "processed_responses.csv"), index=False)

    desc = {
        "input_sha256": sha256(DATA),
        "n_rows": int(len(df)),
        "cohort_counts": {k: int(v) for k, v in cohort_counts.items()},
        "empty_responses": int(empty),
        "length_by_cohort": length,
        "theme_by_cohort": themes,
        "codebook": CODEBOOK,
        "matched_surface_forms": audit,
        "fisher_available": fisher_exact is not None,
    }
    with open(os.path.join(OUT_DIR, "descriptives.json"), "w", encoding="utf-8") as f:
        json.dump(desc, f, indent=2, ensure_ascii=False)
    print("wrote outputs/processed_responses.csv and outputs/descriptives.json")


if __name__ == "__main__":
    sys.exit(main())
