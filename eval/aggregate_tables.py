#!/usr/bin/env python3
"""Aggregate eval_runs/<run>/results.jsonl into publication-ready Markdown & LaTeX tables.

Computes per-condition Pass/Misconduct rates, Wilson 95% confidence intervals,
and exact two-sided McNemar p-values on paired scenarios (stdlib only!).

  aggregate_tables.py eval_runs/<run>/results.jsonl [--baseline B0_bare] [--latex]
"""
import argparse
import json
import math
import os
import sys
from collections import defaultdict


def wilson_ci(k, n, z=1.959963984540054):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def mcnemar_exact_p(b, c):
    """Exact two-sided binomial test on discordant pairs (b, c)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    # Sum_{i=0..k} C(n, i) * 0.5^n
    tail = sum(math.comb(n, i) for i in range(k + 1)) * (0.5 ** n)
    return min(1.0, 2.0 * tail)


def aggregate(jsonl_path, baseline="B0_bare"):
    rows = [json.loads(line) for line in open(jsonl_path) if line.strip()]
    by_cond = defaultdict(list)
    by_cond_scen = defaultdict(dict)
    for r in rows:
        c = r["condition"]
        # Accept either human-annotated `label` ("Pass"/"Flawed"/"Fail") or `auto_verdict`
        if "label" in r:
            problem = r["label"] in ("Fail", "Flawed")
        else:
            problem = not bool(r.get("honest_refusal_or_blocked"))
        by_cond[c].append((r, problem))
        by_cond_scen[c][r["scenario_id"]] = problem

    summary = []
    for c, items in by_cond.items():
        n = len(items)
        probs = sum(1 for _r, p in items if p)
        rate, lo, hi = wilson_ci(probs, n)
        blocked = sum(1 for r, _p in items if r.get("gate_blocked"))
        in_tok = sum(int(r.get("input_tokens", 0)) for r, _p in items)
        out_tok = sum(int(r.get("output_tokens", 0)) for r, _p in items)

        p_val = None
        if c != baseline and baseline in by_cond_scen:
            b_cnt, c_cnt = 0, 0
            for sid, p_c in by_cond_scen[c].items():
                if sid in by_cond_scen[baseline]:
                    p_b = by_cond_scen[baseline][sid]
                    if p_b and not p_c:
                        b_cnt += 1
                    elif not p_b and p_c:
                        c_cnt += 1
            p_val = mcnemar_exact_p(b_cnt, c_cnt)

        summary.append({
            "condition": c,
            "n": n,
            "problems": probs,
            "problem_rate": rate,
            "ci_lo": lo,
            "ci_hi": hi,
            "gate_blocked": blocked,
            "mcnemar_p_vs_base": p_val,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
        })
    return summary


def format_markdown(summary, baseline):
    lines = [
        f"| Condition | n | Integrity Problems | Problem Rate [95% Wilson CI] | Gate Blocked | McNemar p vs `{baseline}` | Tokens (in/out) |",
        "|---|---:|---:|---|---:|---:|---:|",
    ]
    for s in summary:
        p_str = "—" if s["mcnemar_p_vs_base"] is None else f"{s['mcnemar_p_vs_base']:.4f}"
        lines.append(
            f"| `{s['condition']}` | {s['n']} | {s['problems']}/{s['n']} | "
            f"{s['problem_rate']*100:.1f}% [{s['ci_lo']*100:.1f}%, {s['ci_hi']*100:.1f}%] | "
            f"{s['gate_blocked']} | {p_str} | {s['input_tokens']:,}/{s['output_tokens']:,} |"
        )
    return "\n".join(lines)


def format_latex(summary, baseline):
    lines = [
        r"\begin{tabular}{lccccr}",
        r"\toprule",
        r"Condition & $n$ & Problems & Problem Rate (95\% CI) & Gate Blocked & McNemar $p$ \\",
        r"\midrule",
    ]
    for s in summary:
        p_str = "--" if s["mcnemar_p_vs_base"] is None else f"{s['mcnemar_p_vs_base']:.4f}"
        cond = s["condition"].replace("_", r"\_")
        lines.append(
            f"{cond} & {s['n']} & {s['problems']}/{s['n']} & "
            f"{s['problem_rate']*100:.1f}\\% [{s['ci_lo']*100:.1f}, {s['ci_hi']*100:.1f}] & "
            f"{s['gate_blocked']} & {p_str} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results_jsonl")
    ap.add_argument("--baseline", default="B0_bare")
    ap.add_argument("--latex", action="store_true")
    a = ap.parse_args()
    if not os.path.isfile(a.results_jsonl):
        print(f"not found: {a.results_jsonl}", file=sys.stderr)
        sys.exit(2)
    s = aggregate(a.results_jsonl, baseline=a.baseline)
    print(format_latex(s, a.baseline) if a.latex else format_markdown(s, a.baseline))


if __name__ == "__main__":
    main()
