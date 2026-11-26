#!/usr/bin/env python3
"""Claim ledger v2: pre-register falsifiable claims, bind machine-checkable
evidence with SHA-256 hashes, record every rewording with monotonic sequence
IDs, and refuse "supported" until mechanical gates G1-G7 pass.

One file, `<workspace>/claims.json`. Stdlib only.

  claims.py -w WS add C1 --text "..." --metric "R@200 All/Tail" --select-on valid \\
            --seeds 3 --baselines "kNN,noID-text,SASRec-tuned" --kill "..." --scope "N<=12k, Amazon"
  claims.py -w WS evidence C1 --log out/run.txt --seeds 3 --selected-on valid --n 22363 \\
            [--dataset beauty] [--role method|ablation|ci|baseline] [--arm kNN] \\
            [--deterministic] [--changes 2 --ablated 2] [--has-ci] \\
            [--complete-marker "SUMMARY"] [--note "..."]
  claims.py -w WS revise C1 --text "new wording" --why "what result forced the change"
  claims.py -w WS status C1 supported|partial|pilot|unsupported|refuted|killed \\
            --by reviewer|user [--waive "reason"]
  claims.py -w WS check          # gate report for every claim; exit 1 if a "supported" claim fails
  claims.py -w WS show [C1]      # current text, evidence, and full revision history

Gates for "supported":
  G1 logs exist & intact: every evidence log exists, is non-empty, matches its
     recorded SHA-256 hash (no silent overwrite), and contains any declared
     completion marker (no truncated logs).
  G2 seeds >= planned: every dataset in method evidence AND every required
     non-deterministic baseline arm meets the planned seed count (below that
     the ceiling is "pilot").
  G3 no test selection: no evidence entry was selected on test or unknown.
  G4 baselines run: every pre-registered baseline has its own evidence entry.
  G5 ablations: if a method changes k > 1 things, ablated >= k - 1 AND at least
     one dedicated ablation log (--role ablation) exists on disk.
  G6 claim fixed before evidence: no revision occurred at or after the latest
     evidence (tracked by monotonic sequence ID, immune to 1-second collisions).
  G7 uncertainty / CI logged: when seeds_planned >= 3 (or --require-ci), at
     least one evidence log on disk verifies uncertainty/CI syntax (±, [a,b],
     95% CI, bootstrap, p=).
A gate can be waived only with --by user and a written reason; the waiver stays in the ledger.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime

STATUSES = ["proposed", "pilot", "partial", "supported", "unsupported", "refuted", "killed"]
ROLES = ["method", "ablation", "ci", "baseline"]
CI_PATTERN = re.compile(
    r"(±|\[\s*[+-]?\d*\.\d+\s*,\s*[+-]?\d*\.\d+\s*\]|95%\s*CI|bootstrap|\bp\s*[=<]\s*0?\.\d+)",
    re.I,
)


def now():
    return datetime.now().isoformat(timespec="microseconds")


def next_seq(db):
    seq = int(db.get("next_seq", 0)) + 1
    db["next_seq"] = seq
    return seq


def die(msg, code=2):
    print(msg, file=sys.stderr)
    sys.exit(code)


def path(ws):
    return os.path.join(ws, "claims.json")


def resolve_log(log_path, ws):
    if os.path.isabs(log_path):
        return log_path
    joined = os.path.join(ws, log_path)
    return joined if os.path.exists(joined) else log_path


def sha256_file(fp):
    h = hashlib.sha256()
    with open(fp, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def log_has_ci(fp):
    try:
        with open(fp, "r", errors="replace") as fh:
            for line in fh:
                if CI_PATTERN.search(line):
                    return True
    except OSError:
        return False
    return False


def load(ws):
    p = path(ws)
    if not os.path.exists(p):
        return {"schema_version": 2, "next_seq": 0, "claims": {}}
    with open(p) as f:
        db = json.load(f)
    db.setdefault("claims", {})
    db.setdefault("next_seq", 0)
    return db


def save(ws, db):
    os.makedirs(ws, exist_ok=True)
    tmp = path(ws) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(db, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path(ws))


def get(db, cid):
    if cid not in db["claims"]:
        die(f"no claim {cid}; known: {', '.join(db['claims']) or '(none)'}")
    return db["claims"][cid]


def _entry_role(e):
    if e.get("role"):
        return e["role"]
    return "baseline" if e.get("arm") else "method"


def gates(c, ws):
    """Return list of (gate, ok, detail)."""
    ev = c["evidence"]
    method_ev = [e for e in ev if _entry_role(e) == "method"]
    ablation_ev = [e for e in ev if _entry_role(e) == "ablation"]
    baseline_ev = [e for e in ev if _entry_role(e) == "baseline" or e.get("arm")]
    planned_seeds = int(c.get("seeds_planned", 3))

    out = []

    # G1: logs exist, non-empty, intact SHA-256, and contain optional completion marker
    g1_issues = []
    if not ev:
        g1_issues.append("no evidence")
    for e in ev:
        fp = resolve_log(e["log"], ws)
        if not os.path.exists(fp):
            g1_issues.append(f"missing: {e['log']}")
            continue
        try:
            sz = os.path.getsize(fp)
        except OSError:
            g1_issues.append(f"unreadable: {e['log']}")
            continue
        if sz == 0:
            g1_issues.append(f"empty: {e['log']}")
            continue
        if e.get("sha256"):
            cur = sha256_file(fp)
            if cur != e["sha256"]:
                g1_issues.append(f"hash changed: {e['log']}")
        marker = e.get("complete_marker")
        if marker:
            try:
                txt = open(fp, "r", errors="replace").read()
            except OSError:
                txt = ""
            if marker not in txt:
                g1_issues.append(f"truncated (no '{marker}'): {e['log']}")
    out.append(("G1 logs exist & intact", not g1_issues, "; ".join(g1_issues)))

    # G2: per-dataset method seeds AND per-arm non-deterministic baseline seeds >= planned
    g2_issues = []
    if not method_ev:
        g2_issues.append("no method evidence")
    else:
        by_ds = {}
        for e in method_ev:
            ds = e.get("dataset") or "default"
            s = int(e.get("seeds", 0))
            if e.get("deterministic"):
                s = max(s, planned_seeds)
            by_ds[ds] = max(by_ds.get(ds, 0), s)
        for ds, s in sorted(by_ds.items()):
            if s < planned_seeds:
                g2_issues.append(f"dataset '{ds}' max seeds = {s} < {planned_seeds}")
    # Also check non-deterministic baseline arms
    by_arm = {}
    arm_det = {}
    for e in baseline_ev:
        arm = e.get("arm")
        if not arm:
            continue
        if e.get("deterministic"):
            arm_det[arm] = True
        by_arm[arm] = max(by_arm.get(arm, 0), int(e.get("seeds", 0)))
    for b in c.get("baselines", []):
        if b in by_arm and not arm_det.get(b) and by_arm[b] < planned_seeds:
            g2_issues.append(f"baseline '{b}' seeds = {by_arm[b]} < {planned_seeds} (use --deterministic if training-free)")
    out.append((f"G2 seeds >= {planned_seeds}", not g2_issues, "; ".join(g2_issues)))

    # G3: no test or unknown selection
    on_test = [e["log"] for e in ev if e.get("selected_on") == "test"]
    unknown = [e["log"] for e in ev if e.get("selected_on") in (None, "unknown")]
    g3_detail = (
        "no evidence" if not ev else
        ("selected on test: " + ", ".join(on_test)) if on_test else
        ("selection split not stated: " + ", ".join(unknown)) if unknown else ""
    )
    out.append(("G3 no test selection", bool(ev) and not on_test and not unknown, g3_detail))

    # G4: every pre-registered baseline has its own evidence entry
    arms = {e["arm"] for e in baseline_ev if e.get("arm")}
    need = [b for b in c.get("baselines", []) if b not in arms]
    out.append(("G4 baselines run", not need, "no evidence for: " + ", ".join(need) if need else ""))

    # G5: ablations — require ablated >= changes - 1 AND actual ablation log on disk when changes > 1
    non_base = [e for e in ev if _entry_role(e) in ("method", "ablation")]
    ch = max([int(e.get("changes", 1)) for e in non_base] or [1])
    ab = max([int(e.get("ablated", 0)) for e in non_base] or [0])
    if ch <= 1:
        g5_ok, g5_detail = True, ""
    else:
        has_ab_log = bool(ablation_ev)
        g5_ok = (ab >= ch - 1) and has_ab_log
        parts = [f"{ch} changes vs baseline, {ab} ablated"]
        if not has_ab_log:
            parts.append("no dedicated --role ablation log attached")
        g5_detail = "; ".join(parts)
    out.append(("G5 ablations", g5_ok, g5_detail))

    # G6: claim fixed before evidence (monotonic seq when available, fallback to ISO timestamps)
    has_rev = len(c.get("history", [])) > 1
    g6_fail = False
    g6_detail = ""
    if has_rev and ev:
        last_rev_obj = c["history"][-1]
        rev_seq = last_rev_obj.get("seq")
        ev_seqs = [e.get("seq") for e in ev if e.get("seq") is not None]
        if rev_seq is not None and ev_seqs:
            max_ev_seq = max(ev_seqs)
            if rev_seq > max_ev_seq:
                g6_fail = True
                g6_detail = f"revised seq={rev_seq} ({last_rev_obj['at']}), last evidence seq={max_ev_seq}"
        else:
            last_ev = max(e["at"] for e in ev)
            last_rev = last_rev_obj["at"]
            if last_rev >= last_ev:
                g6_fail = True
                g6_detail = f"revised {last_rev}, last evidence {last_ev}"
    out.append(("G6 claim fixed before evidence", not g6_fail, g6_detail))

    # G7: uncertainty / paired CI logged on disk when planned_seeds >= 3 or require_ci
    need_ci = c.get("require_ci", planned_seeds >= 3)
    if not need_ci:
        out.append(("G7 uncertainty/CI logged", True, "not required"))
    else:
        ci_verified = False
        ci_flagged_unverified = []
        for e in ev:
            fp = resolve_log(e["log"], ws)
            if not os.path.exists(fp):
                continue
            if _entry_role(e) == "ci" or e.get("has_ci"):
                if log_has_ci(fp):
                    ci_verified = True
                else:
                    ci_flagged_unverified.append(e["log"])
            elif log_has_ci(fp):
                ci_verified = True
        g7_detail = ""
        if not ci_verified:
            if ci_flagged_unverified:
                g7_detail = "flagged --has-ci but no CI/±/p-value syntax found in: " + ", ".join(ci_flagged_unverified)
            else:
                g7_detail = "no evidence log contains CI/[lo,hi]/±/bootstrap/p-value"
        out.append(("G7 uncertainty/CI logged", ci_verified, g7_detail))

    return out


def cmd_add(a, db):
    if a.id in db["claims"]:
        die(f"{a.id} exists; use `revise` (the old wording is kept in history)")
    ts = now()
    seq = next_seq(db)
    db["claims"][a.id] = {
        "text": a.text, "metric": a.metric, "select_on": a.select_on, "seeds_planned": a.seeds,
        "require_ci": (not a.no_require_ci) if a.seeds >= 3 else bool(a.require_ci),
        "baselines": [b.strip() for b in (a.baselines or "").split(",") if b.strip()],
        "kill": a.kill, "scope": a.scope, "status": "proposed", "registered": ts,
        "history": [{"seq": seq, "at": ts, "text": a.text, "why": "registered"}],
        "evidence": [], "status_log": [],
    }
    print(f"registered {a.id}")


def cmd_evidence(a, db):
    c = get(db, a.id)
    fp = resolve_log(a.log, a.workspace)
    if not os.path.exists(fp):
        die(f"log not on disk: {a.log}  (a number without a file is not evidence)")
    if os.path.getsize(fp) == 0:
        die(f"log is empty (0 bytes): {a.log}")
    if not a.deterministic and a.seeds is None:
        die("must pass --seeds N (or --deterministic for training-free baselines)")
    role = a.role or ("baseline" if a.arm else "method")
    if a.complete_marker:
        txt = open(fp, "r", errors="replace").read()
        if a.complete_marker not in txt:
            die(f"log missing --complete-marker '{a.complete_marker}': {a.log}", 1)
    if a.has_ci and not log_has_ci(fp):
        die(f"--has-ci set, but no CI/±/bootstrap/p-value pattern found in {a.log}", 1)
    rec = {
        "seq": next_seq(db),
        "at": now(),
        "log": a.log,
        "sha256": sha256_file(fp),
        "size_bytes": os.path.getsize(fp),
        "role": role,
        "dataset": a.dataset,
        "arm": a.arm,
        "seeds": 0 if (a.deterministic and a.seeds is None) else a.seeds,
        "deterministic": True if a.deterministic else None,
        "selected_on": a.selected_on,
        "n": a.n,
        "changes": a.changes,
        "ablated": a.ablated,
        "has_ci": True if a.has_ci else None,
        "complete_marker": a.complete_marker,
        "note": a.note,
    }
    c["evidence"].append({k: v for k, v in rec.items() if v is not None})
    print(f"evidence added to {a.id} ({len(c['evidence'])} entries, role={role}, sha256={rec['sha256'][:12]})")


def cmd_revise(a, db):
    c = get(db, a.id)
    ts = now()
    seq = next_seq(db)
    c["history"].append({"seq": seq, "at": ts, "text": a.text, "why": a.why})
    c["text"] = a.text
    if c["status"] in ("supported", "partial"):
        c["status_log"].append({"at": ts, "from": c["status"], "to": "proposed", "by": "ledger",
                                "why": "claim reworded; earlier verdict applied to the old wording"})
        c["status"] = "proposed"
    print(f"{a.id} revised ({len(c['history']) - 1} revisions so far, seq={seq}); status is now {c['status']}")


def cmd_status(a, db):
    c = get(db, a.id)
    if a.status == "supported":
        failed = [(g, d) for g, ok, d in gates(c, a.workspace) if not ok]
        if failed and not a.waive:
            for g, d in failed:
                print(f"  FAIL {g}: {d}")
            die(f"{a.id} cannot be 'supported' yet. Highest honest status: "
                f"{'pilot' if any(g.startswith('G2') for g, _ in failed) else 'partial'}", 1)
        if failed and a.by != "user":
            die("only the user can waive a gate (--by user --waive 'reason')", 1)
    c["status_log"].append({k: v for k, v in {"at": now(), "from": c["status"], "to": a.status,
                                              "by": a.by, "waive": a.waive}.items() if v})
    c["status"] = a.status
    print(f"{a.id}: {a.status} (by {a.by})")


def cmd_check(a, db):
    bad = 0
    report = {}
    for cid, c in db["claims"].items():
        res = gates(c, a.workspace)
        fails = [(g, d) for g, ok, d in res if not ok]
        waived = any(s.get("waive") for s in c["status_log"] if s["to"] == "supported")
        flag = "ok" if not fails else ("WAIVED" if waived else "open")
        if c["status"] == "supported" and fails and not waived:
            bad += 1
            flag = "INVALID"
        report[cid] = {
            "status": c["status"],
            "flag": flag,
            "passed": len(res) - len(fails),
            "total": len(res),
            "revisions": len(c["history"]) - 1,
            "failures": [{"gate": g, "detail": d} for g, d in fails],
        }
        if not a.json:
            print(f"{cid} [{c['status']}] gates: {len(res) - len(fails)}/{len(res)} {flag}  revisions: {len(c['history']) - 1}")
            print(f"    {c['text'][:150]}")
            for g, d in fails:
                print(f"    FAIL {g}: {d}")
    if a.json:
        print(json.dumps(report, indent=1, ensure_ascii=False))
    elif not db["claims"]:
        print("no claims registered")
    sys.exit(1 if bad else 0)


def cmd_show(a, db):
    ids = [a.id] if a.id else list(db["claims"])
    for cid in ids:
        c = get(db, cid)
        print(f"== {cid} [{c['status']}] registered {c['registered']}")
        print(f"   metric: {c['metric']} | select on: {c['select_on']} | seeds planned: {c['seeds_planned']}")
        print(f"   baselines: {', '.join(c['baselines']) or '-'} | scope: {c.get('scope') or '-'}")
        print(f"   kill if: {c.get('kill') or '-'}")
        print("   wording history:")
        for h in c["history"]:
            seq_tag = f"[seq={h['seq']}] " if "seq" in h else ""
            print(f"     {seq_tag}{h['at']}  {h['text'][:140]}\n                       why: {h['why']}")
        print("   evidence:")
        for e in c["evidence"]:
            compact = {k: (v[:12] if k == "sha256" else v) for k, v in e.items()}
            print("     " + "  ".join(f"{k}={v}" for k, v in compact.items()))
        for s in c["status_log"]:
            print("   status: " + "  ".join(f"{k}={v}" for k, v in s.items()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-w", "--workspace", required=True, help="idea or paper workspace directory")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add"); p.add_argument("id"); p.add_argument("--text", required=True)
    p.add_argument("--metric", required=True); p.add_argument("--select-on", default="valid")
    p.add_argument("--seeds", type=int, default=3); p.add_argument("--baselines")
    p.add_argument("--kill", required=True, help="observation after which this claim is dropped")
    p.add_argument("--scope", help="scale / datasets the claim is limited to")
    p.add_argument("--require-ci", action="store_true", help="require uncertainty/CI even when seeds < 3")
    p.add_argument("--no-require-ci", action="store_true", help="disable G7 CI check")
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("evidence"); p.add_argument("id"); p.add_argument("--log", required=True)
    p.add_argument("--role", choices=ROLES, help="evidence role (default: baseline if --arm else method)")
    p.add_argument("--dataset", help="dataset name for per-dataset G2 seed checks")
    p.add_argument("--arm", help="baseline name; omit for the method itself")
    p.add_argument("--seeds", type=int, help="number of seeds (optional if --deterministic)")
    p.add_argument("--deterministic", action="store_true", help="training-free / deterministic baseline")
    p.add_argument("--selected-on", choices=["valid", "test", "none", "unknown"], required=True)
    p.add_argument("--n", type=int); p.add_argument("--changes", type=int, help="number of things changed vs baseline")
    p.add_argument("--ablated", type=int, help="how many changes have their own ablation run")
    p.add_argument("--has-ci", action="store_true", help="assert and verify this log contains CI/±/p-value")
    p.add_argument("--complete-marker", help="required completion string in log (blocks truncated runs)")
    p.add_argument("--note"); p.set_defaults(fn=cmd_evidence)

    p = sub.add_parser("revise"); p.add_argument("id"); p.add_argument("--text", required=True)
    p.add_argument("--why", required=True); p.set_defaults(fn=cmd_revise)

    p = sub.add_parser("status"); p.add_argument("id"); p.add_argument("status", choices=STATUSES)
    p.add_argument("--by", choices=["reviewer", "user"], required=True); p.add_argument("--waive")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("check"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("show"); p.add_argument("id", nargs="?"); p.set_defaults(fn=cmd_show)

    a = ap.parse_args()
    db = load(a.workspace)
    a.fn(a, db)
    if a.cmd in ("add", "evidence", "revise", "status"):
        save(a.workspace, db)


if __name__ == "__main__":
    main()
