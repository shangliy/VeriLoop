"""Step 2: LLM-assisted thematic analysis via the Anthropic Messages API.

Model  : claude-3-5-sonnet-20241022 (fixed by the task spec)
Input  : outputs/processed_responses.csv, outputs/descriptives.json (scripted counts)
Output : outputs/anthropic_messages_response.json  -- ONLY written on a successful API call
         out/llm_thematic_analysis.txt             -- run log, always written (incl. failures)

Behaviour is deliberately strict: if no ANTHROPIC_API_KEY is available, or the API
call fails, this script records the raw evidence and writes NO response file, so no
LLM output is ever fabricated or substituted.
"""
import json
import os
import sys
import traceback

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_JSON = os.path.join(ROOT, "outputs", "anthropic_messages_response.json")
STATUS_TXT = os.path.join(ROOT, "out", "llm_thematic_analysis.txt")
MODEL = "claude-3-5-sonnet-20241022"


def log(msg: str) -> None:
    print(msg, flush=True)


def build_prompt(df: pd.DataFrame, desc: dict) -> str:
    lines = []
    for _, r in df.iterrows():
        lines.append(f"[{r['respondent_id']} | cohort={r['cohort']}] {r['text']}")
    counts = {
        "cohort_counts": desc["cohort_counts"],
        "theme_by_cohort_counts": {
            t: {c: v[c]["n_with_theme"] for c in desc["cohort_counts"]}
            for t, v in desc["theme_by_cohort"].items()
        },
    }
    return (
        "You are assisting a mixed-methods qualitative analysis of semi-structured interview "
        "excerpts about a transit app. Respondents are in two cohorts: transit_primary and "
        "car_primary.\n\n"
        "Scripted descriptive counts (computed by code, treat as ground truth for numbers):\n"
        f"{json.dumps(counts, indent=1)}\n\n"
        "Interview excerpts (one per respondent):\n" + "\n".join(lines) + "\n\n"
        "Task: perform inductive thematic analysis. Return a JSON object with keys: "
        "`themes` (list of objects with `name`, `definition`, `supporting_respondent_ids`, "
        "`cohort_pattern`), `cross_cohort_contrasts` (list of strings), and `caveats` "
        "(list of strings). Only cite respondent IDs that appear above. Do not invent counts; "
        "use the scripted counts when stating frequencies. Output only the JSON object."
    )


def main() -> int:
    log(f"model: {MODEL}")
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    log(f"ANTHROPIC_API_KEY present in environment: {bool(key)}")
    if not key:
        log("STATUS: BLOCKED - no ANTHROPIC_API_KEY in environment; no API call attempted.")
        log("No outputs/anthropic_messages_response.json written (no fabricated LLM output).")
        return 0

    try:
        import anthropic  # noqa: WPS433
    except ImportError as e:
        log(f"STATUS: BLOCKED - anthropic SDK import failed: {e}")
        return 0

    proc = pd.read_csv(os.path.join(ROOT, "outputs", "processed_responses.csv"), dtype=str,
                       keep_default_na=False)
    proc["n_words"] = proc["n_words"].astype(int)
    with open(os.path.join(ROOT, "outputs", "descriptives.json"), encoding="utf-8") as f:
        desc = json.load(f)
    prompt = build_prompt(proc, desc)
    log(f"prompt chars: {len(prompt)}; respondents: {len(proc)}")

    try:
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:  # record the raw failure; do not write any response file
        log("STATUS: API_ERROR - Messages API call failed; no response file written.")
        log(f"exception type: {type(e).__name__}")
        log(f"exception: {e}")
        log(traceback.format_exc())
        return 0

    payload = resp.model_dump(mode="json")
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    log(f"STATUS: OK - saved full response to outputs/{os.path.basename(OUT_JSON)}")
    log(f"response model: {payload.get('model')}; stop_reason: {payload.get('stop_reason')}; "
        f"usage: {payload.get('usage')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
