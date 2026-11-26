"""LLM-assisted structured triage via the Google Generative AI (Gemini) API.

Model is fixed to gemini-1.5-pro. The API key is read from the environment
variable GEMINI_API_KEY (or GOOGLE_API_KEY); it is never written to disk.
The verbatim JSON response is saved to outputs/gemini_raw.json.
If no key is available the script exits with status 2 and writes nothing,
so no placeholder output can be mistaken for a real API response.

Usage: python3 code/llm_triage.py
"""
import csv
import json
import os
import sys
import urllib.error
import urllib.request

MODEL = "gemini-1.5-pro"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(WS, "data", "incident_narratives.csv")
TAB = os.path.join(WS, "out", "tables")
RAW = os.path.join(WS, "outputs", "gemini_raw.json")
OUTDIR = os.path.join(WS, "outputs")


def read_tables():
    def rd(name):
        with open(os.path.join(TAB, name), newline="", encoding="utf-8") as fh:
            return list(csv.reader(fh))
    return {
        "counts_by_source": rd("counts_by_source.csv"),
        "length_by_source": rd("length_by_source.csv"),
        "keyword_group_by_source": rd("keyword_group_by_source.csv"),
    }


def build_prompt(rows, tables):
    lines = []
    for r in rows:
        lines.append(f"- {r['incident_id']} | source_system={r['source_system']} | {r['narrative_text']}")
    tbl = []
    for k, v in tables.items():
        tbl.append(f"## {k}")
        tbl.extend(",".join(row) for row in v)
    return f"""You are assisting a SOC team with structured triage of short synthetic incident narratives.
Task:
1. Propose a compact label set of at most 5 coarse tactic-style categories (e.g. execution, credential access, command-and-control/network, impact/containment, benign/false-positive). Assign each incident exactly one primary label and one priority bucket (P1/P2/P3) with a one-sentence justification tied ONLY to the narrative text.
2. Summarize recurring patterns across the narratives.
3. Contrast what tends to appear more under source_system=edr versus source_system=network_ids. Use tentative language and explicitly note the small sample (3 per group).

Strict rules:
- Do NOT invent IOCs (hashes, IPs, domains, file names, usernames) that are not literally present in the narratives.
- Do NOT state any quantitative claim that is not in the computed summary tables below. Refer to counts only as given in those tables.
- Ground every interpretation in quoted or paraphrased narrative text.
- Respond as JSON with keys: "label_set" (list of {{name, definition}}), "incident_labels" (list of {{incident_id, tactic_label, priority, justification}}), "recurring_patterns" (list of strings), "source_contrast" (list of strings with explicit small-N caveat), "limitations" (list of strings).

Incident narratives:
{chr(10).join(lines)}

Computed summary tables (from code/analyze.py):
{chr(10).join(tbl)}
"""


def main():
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("ERROR: no GEMINI_API_KEY / GOOGLE_API_KEY in environment; LLM step not executed. "
              "No outputs/gemini_raw.json written.", file=sys.stderr)
        sys.exit(2)

    with open(DATA, newline="", encoding="utf-8") as fh:
        rows = [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(fh)]
    prompt = build_prompt(rows, read_tables())

    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    req = urllib.request.Request(
        URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw_text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"ERROR: Gemini API HTTP {e.code}: {e.read().decode('utf-8', 'replace')}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUTDIR, exist_ok=True)
    with open(RAW, "w", encoding="utf-8") as fh:
        fh.write(raw_text)  # verbatim response body
    parsed = json.loads(raw_text)
    try:
        text = parsed["candidates"][0]["content"]["parts"][0]["text"]
        print("[llm] received", len(text), "chars of model text")
    except (KeyError, IndexError):
        print("[llm] response had no candidate text; see outputs/gemini_raw.json", file=sys.stderr)
        sys.exit(1)
    print(f"[llm] model={MODEL} saved outputs/gemini_raw.json")


if __name__ == "__main__":
    main()
