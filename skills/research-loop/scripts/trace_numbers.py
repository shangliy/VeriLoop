#!/usr/bin/env python3
"""Trace every number in a report back to raw logs on disk (v2).

Upgrades over v1 (from real 5-step dry-run findings):
  1. SIGN MISMATCH: preserves leading +/- signs and catches sign-flip fabrications
     (e.g., log says -0.0106, report writes +0.0106).
  2. WRONG LOG: if a table row (or inline backtick) names a specific log file
     (e.g. `fg_noid_all3.txt`), every number on that row MUST exist in the cited
     log file(s), not merely somewhere else among 50 unrelated logs.
  3. UNPAIRED PM / CI: verifies `mean±std` pairs and `[lo, hi]` CI pairs appear
     together on the same line of a log file.
  4. CITED STALE vs WORKSPACE STALE: distinguishes stale logs actually referenced
     or matched by the report from unrelated stale logs in the workspace.

Exit code:
  0  all numbers traced cleanly (0 untraced, 0 sign mismatches, 0 wrong-log, 0 unpaired)
  1  one or more integrity defects found (UNTRACED / SIGN MISMATCH / WRONG LOG / UNPAIRED)
  2  usage error
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP, InvalidOperation

# Capture optional sign only when preceded by whitespace, start, or delimiter (not word/digit/dot)
NUM = re.compile(r"(?<![\w.])([+-]?)(\d*\.\d+)(?![\w]|\.\d)")
PM_PAIR = re.compile(r"(?<![\w.])([+-]?\d*\.\d+)\s*±\s*(\d*\.\d+)(?![\w]|\.\d)")
CI_PAIR = re.compile(r"\[\s*([+-]?\d*\.\d+)\s*,\s*([+-]?\d*\.\d+)\s*\]")
ARXIV = re.compile(r"\b\d{4}\.\d{4,5}(v\d+)?\b")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
LOG_NAME_RE = re.compile(r"\b([A-Za-z0-9_.-]+\.(?:txt|log|out|json|jsonl|csv|tsv))\b")
TEXT_EXT = {".txt", ".log", ".out", ".json", ".jsonl", ".csv", ".tsv", ".md", ".yaml", ".yml", ""}
MAX_D = 6
COMMON_FILES = 8
SPECIFIC_FILES = 3


def _mask_non_metrics(line):
    # Normalize Unicode minus sign (U+2212) to ASCII hyphen-minus so signed
    # values like "−0.004" match "-0.004" in logs without false SIGN_MISMATCH,
    # and normalize ASCII "+/-" to "±" so "0.6470+/-0.0030" doesn't parse "-0.0030" as negative.
    s = line.replace("\u2212", "-").replace("+/-", "\u00b1")
    s = ARXIV.sub(lambda m: " " * len(m.group(0)), s)
    s = DATE_RE.sub(lambda m: " " * len(m.group(0)), s)
    return s


SPACED_MINUS_RE = re.compile(r"(?:^|[\s(=])-\s+$")


PCT_SUFFIX_RE = re.compile(r"^\s*(?:\\?%|pp\b|percentage\s+points?\b)", re.I)


def numbers_in(line):
    """Yield (raw_token, sign_char, abs_Decimal, decimals, is_percent) for decimals in a line."""
    masked = _mask_non_metrics(line)
    for m in NUM.finditer(masked):
        sign = m.group(1)  # '+', '-', or ''
        mag_tok = m.group(2)
        if not sign and SPACED_MINUS_RE.search(masked[:m.start()]):
            # Space-separated binary subtraction (e.g. "53.989 - 0.4438*P") or spaced range
            sign = "~"
        try:
            val = Decimal(mag_tok if mag_tok[0] != "." else "0" + mag_tok)
        except InvalidOperation:
            continue
        dec = len(mag_tok.split(".")[1])
        pct = bool(PCT_SUFFIX_RE.match(masked[m.end():m.end() + 20]))
        yield ("" if sign == "~" else sign) + mag_tok, sign, val, dec, pct


def log_files(paths, skip):
    out = []
    for p in paths:
        if os.path.isfile(p):
            out.append(p)
            continue
        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for f in files:
                if os.path.splitext(f)[1].lower() in TEXT_EXT:
                    out.append(os.path.join(root, f))
    skip = os.path.realpath(skip)
    return sorted({f for f in out if os.path.realpath(f) != skip})


def _keys_for(val, dec):
    keys = {(dec, str(val))}
    for d in range(1, min(dec, MAX_D) + 1):
        q = Decimal(1).scaleb(-d)
        keys.add((d, str(val.quantize(q, rounding=ROUND_HALF_UP))))
        keys.add((d, str(val.quantize(q, rounding=ROUND_HALF_EVEN))))
    return keys


def _signed_tag(sign, val):
    if val == 0:
        return "0"
    if sign == "~":
        return "~"
    return "-" if sign == "-" else "+"


def build_index(files, max_bytes):
    """Build unsigned index, signed index, and per-(file, line) token sets."""
    idx_unsigned = defaultdict(dict)  # (dec, str) -> {file: first_ln}
    idx_signed = defaultdict(dict)    # (sign_tag, dec, str) -> {file: first_ln}
    line_keys = {}                    # file -> list of (ln, set of (sign_tag, dec, str))
    skipped = []
    for f in files:
        try:
            if os.path.getsize(f) > max_bytes:
                skipped.append(f)
                continue
            flines = []
            with open(f, "r", errors="replace") as fh:
                for ln, line in enumerate(fh, 1):
                    if not any(c.isdigit() for c in line):
                        continue
                    lk = set()
                    for _tok, sign, val, dec, _pct in numbers_in(line):
                        stag = _signed_tag(sign, val)
                        stags = ("+", "-") if stag == "~" else (stag,)
                        for k in _keys_for(val, dec):
                            idx_unsigned[k].setdefault(f, ln)
                            for st in stags:
                                sk = (st, k[0], k[1])
                                idx_signed[sk].setdefault(f, ln)
                                lk.add(sk)
                    if lk:
                        flines.append((ln, lk))
            line_keys[f] = flines
        except OSError:
            skipped.append(f)
    return idx_unsigned, idx_signed, line_keys, skipped


def _candidate_keys(val, dec, pct):
    cands = [(val, min(dec, MAX_D))]
    if pct or (Decimal(1) < val <= Decimal(100)):
        cands.append((val / Decimal(100), min(dec + 2, MAX_D)))
    if not pct and (Decimal(0) < val <= Decimal(1)) and dec >= 3:
        cands.append((val * Decimal(100), max(1, min(dec - 2, MAX_D))))
    out = []
    seen = set()
    for v, d in cands:
        q = Decimal(1).scaleb(-d)
        k_main = (d, str(v.quantize(q)))
        if k_main not in seen:
            seen.add(k_main)
            out.append(k_main)
        norm = v.normalize()
        nd = max(0, -norm.as_tuple().exponent)
        for kd in range(max(1, nd), d):
            kq = Decimal(1).scaleb(-kd)
            k_sub = (kd, str(v.quantize(kq)))
            if k_sub not in seen:
                seen.add(k_sub)
                out.append(k_sub)
    return out


def lookup(idx_unsigned, idx_signed, sign, val, dec, pct, allowed_files=None):
    """Return (signed_hits, unsigned_hits) optionally restricted to allowed_files."""
    signed_hits, unsigned_hits = {}, {}
    stag = _signed_tag(sign, val)
    for k in _candidate_keys(val, dec, pct):
        uh = idx_unsigned.get(k, {})
        if stag in ("0", "~"):
            sh = uh
        else:
            sh = idx_signed.get((stag, k[0], k[1]), {})
        if allowed_files is not None:
            uh = {f: l for f, l in uh.items() if f in allowed_files}
            sh = {f: l for f, l in sh.items() if f in allowed_files}
        unsigned_hits.update(uh)
        signed_hits.update(sh)
    return signed_hits, unsigned_hits


def pair_on_same_line(line_keys, a_str, b_str, allowed_files=None):
    """Check whether two signed decimals co-occur on the same line of any allowed log."""
    def parse_one(s):
        sign = "-" if s.startswith("-") else ("+" if s.startswith("+") else "")
        mag = s.lstrip("+-")
        val = Decimal(mag if mag[0] != "." else "0" + mag)
        dec = len(mag.split(".")[1])
        return _signed_tag(sign, val), _candidate_keys(val, min(dec, MAX_D), False)

    try:
        sa, ka = parse_one(a_str)
        sb, kb = parse_one(b_str)
    except InvalidOperation:
        return True
    files_to_check = allowed_files if allowed_files is not None else line_keys.keys()
    for f in files_to_check:
        for _ln, lk in line_keys.get(f, ()):
            a_ok = any(((sa, d, s) in lk) if sa != "0" else any((t, d, s) in lk for t in ("0", "+", "-")) for d, s in ka)
            if not a_ok:
                continue
            b_ok = any(((sb, d, s) in lk) if sb != "0" else any((t, d, s) in lk for t in ("0", "+", "-")) for d, s in kb)
            if b_ok:
                return True
    return False


def stale_logs(files, scripts_dir):
    if not scripts_dir or not os.path.isdir(scripts_dir):
        return []
    scripts = {}
    for root, _d, fs in os.walk(scripts_dir):
        for f in fs:
            if f.endswith((".py", ".sh", ".ipynb")):
                scripts[os.path.splitext(f)[0]] = os.path.join(root, f)
    out = []
    for f in files:
        stem = os.path.splitext(os.path.basename(f))[0]
        s = scripts.get(stem)
        if s and os.path.getmtime(s) > os.path.getmtime(f) + 1:
            out.append((f, s))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report")
    ap.add_argument("--logs", action="append", required=True, help="log file or directory (repeatable)")
    ap.add_argument("--scripts", help="scripts dir, to flag logs older than their script")
    ap.add_argument("--min-decimals", type=int, default=3,
                    help="ignore numbers with fewer decimals (default 3)")
    ap.add_argument("--max-mb", type=float, default=50.0, help="skip log files larger than this")
    ap.add_argument("--strict-stale", action="store_true", help="exit 1 if any cited log is stale")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if not os.path.isfile(a.report):
        print(f"no such report: {a.report}", file=sys.stderr)
        sys.exit(2)
    files = log_files(a.logs, a.report)
    if not files:
        print("no log files found under --logs", file=sys.stderr)
        sys.exit(2)

    by_basename = defaultdict(set)
    for f in files:
        by_basename[os.path.basename(f)].add(f)

    idx_u, idx_s, line_keys, skipped = build_index(files, int(a.max_mb * 1e6))

    traced, untraced, sign_mismatches, wrong_logs = [], [], [], []
    common, mixed, unpaired_pairs = [], [], []
    cited_log_set = set()
    in_code = False

    with open(a.report, "r", errors="replace") as fh:
        for ln, line in enumerate(fh, 1):
            if line.lstrip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue

            # Detect explicitly cited log files on this line (especially table rows)
            row_cited = set()
            for m in LOG_NAME_RE.finditer(line):
                bn = m.group(1)
                if bn in by_basename:
                    row_cited.update(by_basename[bn])
                    cited_log_set.update(by_basename[bn])

            is_table_row = line.lstrip().startswith("|")
            enforce_cited = is_table_row and bool(row_cited)
            row_sets = []

            for raw_tok, sign, val, dec, pct in numbers_in(line):
                if dec < a.min_decimals:
                    continue
                rec = {"line": ln, "number": raw_tok + ("%" if pct else ""), "context": line.strip()[:160]}

                # First check against row-cited logs if present on a table row
                if enforce_cited:
                    sh_c, uh_c = lookup(idx_u, idx_s, sign, val, min(dec, MAX_D), pct, allowed_files=row_cited)
                    if sh_c:
                        rec["sources"] = sorted(f"{os.path.relpath(f)}:{l}" for f, l in sh_c.items())[:4]
                        rec["n_files"] = len(sh_c)
                        traced.append(rec)
                        if len(sh_c) <= SPECIFIC_FILES:
                            row_sets.append((raw_tok, set(sh_c)))
                        continue
                    elif uh_c:
                        rec["cited_logs"] = sorted(os.path.basename(f) for f in row_cited)
                        rec["opposite_sign_sources"] = sorted(f"{os.path.relpath(f)}:{l}" for f, l in uh_c.items())[:4]
                        sign_mismatches.append(rec)
                        continue
                    else:
                        # Not in cited log — check globally to distinguish WRONG LOG vs UNTRACED
                        sh_g, uh_g = lookup(idx_u, idx_s, sign, val, min(dec, MAX_D), pct)
                        if sh_g:
                            rec["cited_logs"] = sorted(os.path.basename(f) for f in row_cited)
                            rec["actual_sources"] = sorted(f"{os.path.relpath(f)}:{l}" for f, l in sh_g.items())[:4]
                            wrong_logs.append(rec)
                            continue
                        elif uh_g:
                            rec["cited_logs"] = sorted(os.path.basename(f) for f in row_cited)
                            rec["opposite_sign_sources"] = sorted(f"{os.path.relpath(f)}:{l}" for f, l in uh_g.items())[:4]
                            sign_mismatches.append(rec)
                            continue
                        else:
                            untraced.append(rec)
                            continue

                # Non-table or no row-cited log: check globally
                sh, uh = lookup(idx_u, idx_s, sign, val, min(dec, MAX_D), pct)
                if sh:
                    rec["sources"] = sorted(f"{os.path.relpath(f)}:{l}" for f, l in sh.items())[:4]
                    rec["n_files"] = len(sh)
                    traced.append(rec)
                    cited_log_set.update(sh.keys())
                    if len(sh) >= COMMON_FILES:
                        common.append(rec)
                    if len(sh) <= SPECIFIC_FILES:
                        row_sets.append((raw_tok, set(sh)))
                elif uh:
                    rec["opposite_sign_sources"] = sorted(f"{os.path.relpath(f)}:{l}" for f, l in uh.items())[:4]
                    sign_mismatches.append(rec)
                else:
                    untraced.append(rec)

            # Check MIXED ROW on table rows
            if is_table_row and len(row_sets) >= 2:
                if not set.intersection(*(s for _t, s in row_sets)):
                    mixed.append({"line": ln, "context": line.strip()[:160],
                                  "by_number": {t: sorted(os.path.basename(f) for f in s) for t, s in row_sets}})

            # Check paired ± and [lo, hi] CI co-occurrence on the same log line
            scope_files = row_cited if enforce_cited else None
            for pm in PM_PAIR.finditer(_mask_non_metrics(line)):
                a_s, b_s = pm.group(1), pm.group(2)
                if len(a_s.split(".")[1]) >= a.min_decimals and len(b_s.split(".")[1]) >= a.min_decimals:
                    if not pair_on_same_line(line_keys, a_s, b_s, allowed_files=scope_files):
                        unpaired_pairs.append({"line": ln, "kind": "PM", "pair": f"{a_s}±{b_s}",
                                               "context": line.strip()[:160]})
            for ci in CI_PAIR.finditer(_mask_non_metrics(line)):
                a_s, b_s = ci.group(1), ci.group(2)
                if len(a_s.split(".")[1]) >= a.min_decimals and len(b_s.split(".")[1]) >= a.min_decimals:
                    if not pair_on_same_line(line_keys, a_s, b_s, allowed_files=scope_files):
                        unpaired_pairs.append({"line": ln, "kind": "CI", "pair": f"[{a_s},{b_s}]",
                                               "context": line.strip()[:160]})

    all_stale = stale_logs(files, a.scripts)
    cited_stale = [(l, s) for l, s in all_stale if l in cited_log_set]
    workspace_stale = [(l, s) for l, s in all_stale if l not in cited_log_set]

    result = {
        "report": a.report,
        "log_files": len(files),
        "skipped_large": skipped,
        "traced": len(traced),
        "untraced": untraced,
        "sign_mismatches": sign_mismatches,
        "wrong_logs": wrong_logs,
        "unpaired_pairs": unpaired_pairs,
        "mixed_rows": mixed,
        "cited_stale": [{"log": l, "script": s} for l, s in cited_stale],
        "workspace_stale": [{"log": l, "script": s} for l, s in workspace_stale],
        "common": len(common),
    }

    if a.json:
        print(json.dumps(result, indent=1, ensure_ascii=False))
    else:
        total = len(traced) + len(untraced) + len(sign_mismatches) + len(wrong_logs)
        print(f"{a.report}: {total} numbers (>= {a.min_decimals} decimals) checked against {len(files)} log files")
        print(f"  traced {len(traced)}   UNTRACED {len(untraced)}   SIGN_MISMATCH {len(sign_mismatches)}   "
              f"WRONG_LOG {len(wrong_logs)}   UNPAIRED_PM/CI {len(unpaired_pairs)}   "
              f"mixed rows {len(mixed)}   cited stale {len(cited_stale)}   workspace stale {len(workspace_stale)}")
        if untraced:
            print("\nUNTRACED (in the report, in no log):")
            by_line = defaultdict(list)
            for r in untraced:
                by_line[r["line"]].append(r)
            for ln in sorted(by_line):
                nums = " ".join(r["number"] for r in by_line[ln])
                print(f"  L{ln}: {nums}\n        | {by_line[ln][0]['context']}")
        if sign_mismatches:
            print("\nSIGN MISMATCH (magnitude exists only with opposite sign):")
            for r in sign_mismatches:
                print(f"  L{r['line']}: {r['number']}  (opposite sign in {', '.join(r['opposite_sign_sources'][:3])})")
                print(f"        | {r['context']}")
        if wrong_logs:
            print("\nWRONG LOG (number not in row's cited log; found elsewhere):")
            for r in wrong_logs:
                print(f"  L{r['line']}: {r['number']}  cited={','.join(r['cited_logs'])}  actual={','.join(r['actual_sources'][:3])}")
                print(f"        | {r['context']}")
        if unpaired_pairs:
            print("\nUNPAIRED PM/CI (pair values never co-occur on the same log line):")
            for r in unpaired_pairs:
                print(f"  L{r['line']} [{r['kind']}]: {r['pair']}\n        | {r['context']}")
        if mixed:
            print("\nMIXED ROWS (no single log holds every number in the row; check for mixed variants/runs):")
            for m in mixed:
                print(f"  L{m['line']}: {m['context']}")
                for t, fs in m["by_number"].items():
                    print(f"        {t:>10}  <- {', '.join(fs[:4])}")
        if cited_stale:
            print("\nCITED STALE (script modified after a log used in this report):")
            for l, s in cited_stale:
                print(f"  {os.path.relpath(l)}  older than  {os.path.relpath(s)}")
        if workspace_stale:
            print("\nWORKSPACE STALE (unrelated log in --logs older than its script):")
            for l, s in workspace_stale:
                print(f"  {os.path.relpath(l)}  older than  {os.path.relpath(s)}")
        if skipped:
            print(f"\nskipped (too large or unreadable): {len(skipped)} files")

    failed = bool(untraced or sign_mismatches or wrong_logs or unpaired_pairs or (a.strict_stale and cited_stale))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
