#!/usr/bin/env python3
"""Static AST & text integrity pre-scanner for research code and reports.

Stdlib only; parses Python files via `ast.parse` and NEVER executes target code.
Targets the highest-frequency integrity failure modes documented by FabScore
(44.6% hardcoded/simulated metrics, 64.6% synthetic/mock data fallback),
SciIntegrity-Bench (T02 test peeking, T05/T08 infeasibility concealment),
ARIS experiment-integrity (dead metric code, scope overclaim), and our own
5-step dry-run (hardcoded `[Ref ...]` prints, optimistic `(sc > st).sum()` ties).

  audit_code.py --scripts scripts/ [--report reports/run.md] [--json] [--strict]

Exit code: 0 clean (or non-strict), 1 HIGH findings present under --strict, 2 usage error.
"""
import argparse
import ast
import json
import os
import re
import sys

METRIC_WORD_RE = re.compile(
    r"(?:^|[^a-zA-Z0-9])(acc(?:uracy)?|f1|auc|auroc|ndcg|recall|precision|mrr|map|r@\d+|bleu|rouge|perplexity|loss|a1|head|tail)(?:$|[^a-zA-Z0-9])",
    re.I,
)
FLOAT_LIT_RE = re.compile(r"(?<![\w.])\d*\.\d{3,}(?![\w])")
PARAM_OR_THRESH_RE = re.compile(
    r"(?:\b(?:tau|beta|alpha|lambda|lam|lr|eps|tol|th|thresh|scale|weight|decay|temp|sigma)\s*=\s*|[<>]=?\s*)\d*\.\d+",
    re.I,
)
REF_PRINT_RE = re.compile(r"\[?\bref\b", re.I)
MOCK_NAME_RE = re.compile(r"(?:^|_)(mock|fake|dummy|synthetic|placeholder|stub)(?:_|$)", re.I)
RANDOM_CALL_ATTRS = {
    "random", "rand", "randn", "randint", "normal", "uniform", "choice",
    "binomial", "poisson", "gauss", "make_classification", "make_regression",
    "make_blobs",
}
TEST_METRIC_RE = re.compile(r"\btest_(?:acc|f1|auc|loss|recall|ndcg|score|metric|r\d+|perf)\b", re.I)
BEST_VAR_RE = re.compile(r"\bbest(?:_|\b)", re.I)
METRIC_FUNC_RE = re.compile(r"^(?:compute|calc|eval|measure|metric|score)_[a-z0-9_]+$", re.I)
OVERCLAIM_RE = re.compile(
    r"\b(universal(?:ly)?|proves?|always\s+(?:beats?|outperforms?)|eliminates?\s+all|"
    r"extensive(?:ly)?|comprehensive(?:ly)?|robust\s+across\s+all|solves?\s+the\s+problem|"
    r"state[- ]of[- ]the[- ]art\s+across\s+all)\b",
    re.I,
)


def _call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _iter_py_files(paths):
    out = []
    for p in paths:
        if os.path.isfile(p) and p.endswith(".py"):
            out.append(p)
        elif os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
                for f in sorted(files):
                    if f.endswith(".py"):
                        out.append(os.path.join(root, f))
    return sorted(set(out))


def _contains_random_or_mock(nodes):
    hits = []
    for sub in nodes:
        for n in ast.walk(sub):
            if isinstance(n, ast.Call):
                cname = _call_name(n.func)
                attr = cname.split(".")[-1]
                if attr == "default_rng" or attr == "seed":
                    continue
                if attr in RANDOM_CALL_ATTRS or ("np.random." in cname and attr != "default_rng"):
                    hits.append((getattr(n, "lineno", 0), cname))
            elif isinstance(n, ast.Name) and MOCK_NAME_RE.search(n.id):
                hits.append((getattr(n, "lineno", 0), n.id))
            elif isinstance(n, ast.Constant) and isinstance(n.value, str) and MOCK_NAME_RE.search(n.value):
                hits.append((getattr(n, "lineno", 0), repr(n.value[:40])))
    return hits


def _is_missing_data_guard(test):
    """Heuristic for `if not os.path.exists(...)`, `if df.empty`, `if len(df) == 0`."""
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        src = ast.dump(test.operand)
        if "exists" in src or "isfile" in src:
            return True
    if isinstance(test, ast.Attribute) and test.attr == "empty":
        return True
    if isinstance(test, ast.Compare) and isinstance(test.left, ast.Call):
        if _call_name(test.left.func) == "len":
            for c in test.comparators:
                if isinstance(c, ast.Constant) and c.value == 0:
                    return True
    return False


def _is_gt_compare(node):
    if not (isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.Gt)):
        return False
    # Ignore threshold checks against numeric constants like (s > 1e-4).sum()
    if isinstance(node.left, ast.Constant) or isinstance(node.comparators[0], ast.Constant):
        return False
    return True


def _has_hardcoded_metric_float(s):
    cleaned = PARAM_OR_THRESH_RE.sub("", s)
    for m in FLOAT_LIT_RE.finditer(cleaned):
        val = float(m.group(0))
        if val != 0.0 and val != 1.0:
            return True
    return False


def scan_python_file(fp):
    findings = []
    try:
        src = open(fp, "r", errors="replace").read()
    except OSError as e:
        return [{"severity": "INFO", "code": "UNREADABLE", "file": fp, "line": 0, "detail": str(e)}]
    lines = src.splitlines()
    try:
        tree = ast.parse(src, filename=fp)
    except SyntaxError as e:
        return [{"severity": "MEDIUM", "code": "SYNTAX_ERROR", "file": fp, "line": e.lineno or 0, "detail": str(e)}]

    def snippet(ln):
        return lines[ln - 1].strip()[:140] if 1 <= ln <= len(lines) else ""

    # 1. Track defined vs called/referenced metric helper functions for DEAD_METRIC_CODE
    has_main_guard = False
    top_defs = {}
    name_uses = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and METRIC_FUNC_RE.match(node.name):
            top_defs[node.name] = node.lineno
        if isinstance(node, ast.If):
            d = ast.dump(node.test)
            if "__name__" in d and "__main__" in d:
                has_main_guard = True

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            name_uses.add(node.id)
        elif isinstance(node, ast.Attribute):
            name_uses.add(node.attr)

        # 2. HARDCODED_REF_PRINT: print/log string literals containing hardcoded metric floats
        if isinstance(node, ast.Call):
            cname = _call_name(node.func)
            if cname in ("print", "logging.info", "logging.warning", "logger.info", "f.write", "fh.write"):
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        s = arg.value
                        if _has_hardcoded_metric_float(s) and (METRIC_WORD_RE.search(s) or REF_PRINT_RE.search(s)):
                            findings.append({
                                "severity": "HIGH",
                                "code": "HARDCODED_REF_PRINT",
                                "file": fp,
                                "line": node.lineno,
                                "detail": f"Constant string prints hardcoded metric float(s): {snippet(node.lineno)}",
                            })
                    elif isinstance(arg, ast.JoinedStr):
                        const_parts = "".join(v.value for v in arg.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
                        if _has_hardcoded_metric_float(const_parts) and (METRIC_WORD_RE.search(const_parts) or REF_PRINT_RE.search(const_parts)):
                            findings.append({
                                "severity": "HIGH",
                                "code": "HARDCODED_REF_PRINT",
                                "file": fp,
                                "line": node.lineno,
                                "detail": f"f-string contains hardcoded literal metric float(s): {snippet(node.lineno)}",
                            })

            # 3. OPTIMISTIC_TIE_BREAKING: (sc > st).sum(...) or sum(sc > st)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "sum" and _is_gt_compare(node.func.value):
                findings.append({
                    "severity": "MEDIUM",
                    "code": "OPTIMISTIC_TIE_BREAKING",
                    "file": fp,
                    "line": node.lineno,
                    "detail": f"Strict '>' rank count treats exact ties optimistically: {snippet(node.lineno)}",
                })
            elif cname in ("sum", "np.sum", "torch.sum") and node.args and _is_gt_compare(node.args[0]):
                findings.append({
                    "severity": "MEDIUM",
                    "code": "OPTIMISTIC_TIE_BREAKING",
                    "file": fp,
                    "line": node.lineno,
                    "detail": f"Strict '>' rank count treats exact ties optimistically: {snippet(node.lineno)}",
                })

        # 4. HARDCODED_METRIC_ARRAY: assigning list/dict of constant floats to a metric-named variable
        if isinstance(node, ast.Assign):
            target_names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            for tn in target_names:
                if METRIC_WORD_RE.search(tn):
                    val = node.value
                    if isinstance(val, (ast.List, ast.Tuple)) and len(val.elts) >= 2:
                        if all(isinstance(e, ast.Constant) and isinstance(e.value, (int, float)) for e in val.elts):
                            if any(isinstance(e.value, float) for e in val.elts):
                                findings.append({
                                    "severity": "HIGH",
                                    "code": "HARDCODED_METRIC_ARRAY",
                                    "file": fp,
                                    "line": node.lineno,
                                    "detail": f"Hardcoded float list assigned to metric variable '{tn}': {snippet(node.lineno)}",
                                })
                    elif isinstance(val, ast.Dict) and len(val.values) >= 2:
                        if all(isinstance(v, ast.Constant) and isinstance(v.value, float) for v in val.values):
                            findings.append({
                                "severity": "HIGH",
                                "code": "HARDCODED_METRIC_ARRAY",
                                "file": fp,
                                "line": node.lineno,
                                "detail": f"Hardcoded float dict assigned to metric variable '{tn}': {snippet(node.lineno)}",
                            })

        # 5. MOCK_OR_SYNTHETIC_FALLBACK: random/mock generation inside except or missing-data if-branch
        if isinstance(node, ast.ExceptHandler):
            hits = _contains_random_or_mock(node.body)
            if hits:
                ln, what = hits[0]
                findings.append({
                    "severity": "HIGH",
                    "code": "MOCK_OR_SYNTHETIC_FALLBACK",
                    "file": fp,
                    "line": ln or node.lineno,
                    "detail": f"Random/mock fallback ({what}) inside except block: {snippet(ln or node.lineno)}",
                })
        elif isinstance(node, ast.If) and _is_missing_data_guard(node.test):
            hits = _contains_random_or_mock(node.body)
            if hits:
                ln, what = hits[0]
                findings.append({
                    "severity": "HIGH",
                    "code": "MOCK_OR_SYNTHETIC_FALLBACK",
                    "file": fp,
                    "line": ln or node.lineno,
                    "detail": f"Random/mock fallback ({what}) when input data is missing/empty: {snippet(ln or node.lineno)}",
                })

        # 6. TEST_SPLIT_TUNING: comparing test metric against best_* in an if-condition
        if isinstance(node, ast.If):
            cond_line = snippet(node.lineno)
            if TEST_METRIC_RE.search(cond_line) and BEST_VAR_RE.search(cond_line):
                findings.append({
                    "severity": "HIGH",
                    "code": "TEST_SPLIT_TUNING",
                    "file": fp,
                    "line": node.lineno,
                    "detail": f"Model/checkpoint selection appears conditioned on test metric: {cond_line}",
                })

    if has_main_guard:
        for fn, ln in top_defs.items():
            if fn not in name_uses:
                findings.append({
                    "severity": "MEDIUM",
                    "code": "DEAD_METRIC_CODE",
                    "file": fp,
                    "line": ln,
                    "detail": f"Metric function '{fn}' is defined but never called in script",
                })

    return findings


def scan_report_scope(report_path):
    findings = []
    if not report_path or not os.path.isfile(report_path):
        return findings
    in_code = False
    with open(report_path, "r", errors="replace") as fh:
        for ln, line in enumerate(fh, 1):
            if line.lstrip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            for m in OVERCLAIM_RE.finditer(line):
                findings.append({
                    "severity": "INFO",
                    "code": "SCOPE_OVERCLAIM_WORD",
                    "file": report_path,
                    "line": ln,
                    "detail": f"Strong scope word '{m.group(0)}' — verify matches registered scope: {line.strip()[:140]}",
                })
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scripts", action="append", required=True, help="Python file or directory (repeatable)")
    ap.add_argument("--report", help="optional report markdown to scan for scope overclaim words")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any HIGH severity finding is detected")
    a = ap.parse_args()

    py_files = _iter_py_files(a.scripts)
    if not py_files:
        print("no .py files found under --scripts", file=sys.stderr)
        sys.exit(2)

    all_findings = []
    for fp in py_files:
        all_findings.extend(scan_python_file(fp))
    if a.report:
        all_findings.extend(scan_report_scope(a.report))

    sev_rank = {"HIGH": 0, "MEDIUM": 1, "INFO": 2}
    all_findings.sort(key=lambda r: (sev_rank.get(r["severity"], 9), r["file"], r["line"]))
    counts = {k: sum(1 for r in all_findings if r["severity"] == k) for k in ("HIGH", "MEDIUM", "INFO")}

    out = {"scripts_scanned": len(py_files), "counts": counts, "findings": all_findings}
    if a.json:
        print(json.dumps(out, indent=1, ensure_ascii=False))
    else:
        print(f"Scanned {len(py_files)} Python scripts" + (f" + {a.report}" if a.report else ""))
        print(f"  HIGH {counts['HIGH']}   MEDIUM {counts['MEDIUM']}   INFO {counts['INFO']}")
        for r in all_findings:
            rel = os.path.relpath(r["file"])
            print(f"  [{r['severity']}] {r['code']}  {rel}:{r['line']}\n        {r['detail']}")

    sys.exit(1 if (a.strict and counts["HIGH"] > 0) else 0)


if __name__ == "__main__":
    main()
