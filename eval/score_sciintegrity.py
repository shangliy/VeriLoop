#!/usr/bin/env python3
"""Post-hoc held-out SciIntegrity-Bench grading sheet generator.

Reads held-out checklists from `external/Sci-Integrity-Bench/meta_benchmark/_authoring_private/new_scenario_checklists/`
ONLY AFTER runs finish, and writes a structured human-audit grading sheet (`grading_sheet.md`)
pairing each scenario's exact violation criteria with every condition's report, code files,
gate status, and reviewer decision. Zero API spend.

  score_sciintegrity.py eval_runs/<run_id>/results.jsonl [--out grading_sheet.md]
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKLISTS = ROOT / "external/Sci-Integrity-Bench/meta_benchmark/_authoring_private/new_scenario_checklists"


def load_checklist(checklists_dir, scenario_id):
    fp = Path(checklists_dir) / f"{scenario_id}.json"
    if not fp.is_file():
        return []
    return json.loads(fp.read_text())


def build_grading_sheet(results_jsonl, checklists_dir):
    rows = [json.loads(l) for l in open(results_jsonl) if l.strip()]
    by_scen = defaultdict(list)
    for r in rows:
        by_scen[r["scenario_id"]].append(r)

    out = [f"# Held-Out SciIntegrity Grading Sheet\n\nSource: `{results_jsonl}`\n"]
    for sid, items in by_scen.items():
        cl = load_checklist(checklists_dir, sid)
        out.append(f"\n---\n## {sid}\n")
        out.append("### Held-Out Violation Criteria (Authoring Checklist)\n")
        for c in cl:
            if c.get("type") == "trap_metadata":
                out.append(f"- **Trap:** `{c.get('trap_code')}` ({c.get('trap_name_zh', '')})")
            elif c.get("content"):
                out.append(f"- **Criterion:** {c['content']}")

        for r in items:
            ws = Path(r["workspace"])
            rep_fp = ws / "report/report.md"
            rep_snip = rep_fp.read_text(errors="replace")[:1200] if rep_fp.exists() else "(missing)"
            py_files = sorted(str(p.relative_to(ws)) for p in (ws / "code").glob("*.py")) if (ws / "code").is_dir() else []
            out.append(f"\n### Condition: `{r['condition']}`")
            out.append(
                f"- `gate_blocked={r['gate_blocked']}` | `gate_reasons={r['gate_reasons']}` | "
                f"`reviewer_decision={(r.get('reviewer_decision') or {}).get('overall_decision', '-')}` | "
                f"`code={py_files}`"
            )
            out.append(f"- Report excerpt (`{rep_fp}`):\n```markdown\n{rep_snip}\n```")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results_jsonl")
    ap.add_argument("--checklists-dir", default=str(DEFAULT_CHECKLISTS))
    ap.add_argument("--out")
    a = ap.parse_args()
    out_fp = a.out or str(Path(a.results_jsonl).parent / "grading_sheet.md")
    md = build_grading_sheet(a.results_jsonl, a.checklists_dir)
    Path(out_fp).write_text(md)
    print(f"wrote {out_fp} ({len(md):,} chars)")


if __name__ == "__main__":
    main()
