#!/usr/bin/env python3
"""API budget ledger & hard circuit breaker for autonomous research evaluations.

Stdlib only. Tracks every LLM call in `<path>/budget_ledger.json` and refuses
calls that would exceed the hard USD cap (default $50.00).

  budget.py -f budget_ledger.json init --limit 50.0
  budget.py -f budget_ledger.json status
  budget.py -f budget_ledger.json check --est 0.50
"""
import argparse
import json
import os
import sys
from datetime import datetime

# Conservative USD per 1M tokens (input, output). Override via env or ledger config.
DEFAULT_PRICING = {
    # Anthropic Claude
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "sonnet": (3.00, 15.00),
    "claude-opus-4-6": (15.00, 75.00),
    "opus": (15.00, 75.00),
    "claude-haiku-4-5": (0.80, 4.00),
    "haiku": (0.80, 4.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    # OpenAI
    "gpt-5.4": (2.50, 15.00),
    "gpt-5": (1.25, 10.00),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "o4-mini": (1.10, 4.40),
    "o3-mini": (1.10, 4.40),
    # Local / dry-run
    "mock": (0.0, 0.0),
    "dry-run": (0.0, 0.0),
}


class BudgetExceededError(RuntimeError):
    """Raised when a planned or recorded API call would exceed the hard cap."""


def now():
    return datetime.now().isoformat(timespec="seconds")


def estimate_cost(model, input_tokens, output_tokens, pricing=None):
    table = dict(DEFAULT_PRICING)
    if pricing:
        table.update(pricing)
    rates = table.get(model)
    if rates is None:
        # Prefix match (e.g. gpt-5.4-2026-05-01 -> gpt-5.4)
        for k in sorted(table, key=len, reverse=True):
            if model.startswith(k):
                rates = table[k]
                break
    if rates is None:
        # Conservative fallback so unknown models cannot silently spend $0
        rates = (5.00, 20.00)
    in_rate, out_rate = rates
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000.0


def load_ledger(fp, default_limit=50.0):
    if not os.path.exists(fp):
        return {
            "limit_usd": float(default_limit),
            "warn_usd": round(float(default_limit) * 0.9, 2),
            "spent_usd": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "pricing_overrides": {},
            "calls": [],
        }
    with open(fp) as fh:
        db = json.load(fh)
    db.setdefault("limit_usd", float(default_limit))
    db.setdefault("warn_usd", round(float(db["limit_usd"]) * 0.9, 2))
    db.setdefault("spent_usd", 0.0)
    db.setdefault("total_input_tokens", 0)
    db.setdefault("total_output_tokens", 0)
    db.setdefault("pricing_overrides", {})
    db.setdefault("calls", [])
    return db


def save_ledger(fp, db):
    parent = os.path.dirname(os.path.abspath(fp))
    os.makedirs(parent, exist_ok=True)
    tmp = fp + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(db, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, fp)


def check_budget(fp, est_usd, default_limit=50.0):
    db = load_ledger(fp, default_limit=default_limit)
    projected = db["spent_usd"] + float(est_usd)
    if projected > db["limit_usd"] + 1e-9:
        raise BudgetExceededError(
            f"Budget circuit breaker tripped: spent=${db['spent_usd']:.4f} + "
            f"est=${est_usd:.4f} = ${projected:.4f} > limit=${db['limit_usd']:.2f}"
        )
    return db


def record_call(fp, provider, model, role, task_id, input_tokens, output_tokens,
                default_limit=50.0, actual_cost_usd=None):
    db = load_ledger(fp, default_limit=default_limit)
    if actual_cost_usd is not None:
        cost = float(actual_cost_usd)
    else:
        cost = estimate_cost(model, int(input_tokens), int(output_tokens), db.get("pricing_overrides"))
    db["spent_usd"] = round(db["spent_usd"] + cost, 6)
    db["total_input_tokens"] += int(input_tokens)
    db["total_output_tokens"] += int(output_tokens)
    entry = {
        "at": now(),
        "provider": provider,
        "model": model,
        "role": role,
        "task_id": task_id,
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "cost_usd": round(cost, 6),
    }
    db["calls"].append(entry)
    save_ledger(fp, db)
    return entry, db


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-f", "--file", required=True, help="path to budget_ledger.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("--limit", type=float, default=50.0)
    p.add_argument("--warn", type=float)

    p = sub.add_parser("status")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("check")
    p.add_argument("--est", type=float, required=True)

    a = ap.parse_args()
    if a.cmd == "init":
        db = load_ledger(a.file, default_limit=a.limit)
        db["limit_usd"] = float(a.limit)
        db["warn_usd"] = float(a.warn) if a.warn is not None else round(float(a.limit) * 0.9, 2)
        save_ledger(a.file, db)
        print(f"initialized {a.file}: limit=${db['limit_usd']:.2f}, warn=${db['warn_usd']:.2f}")
    elif a.cmd == "status":
        db = load_ledger(a.file)
        if a.json:
            print(json.dumps(db, indent=1, ensure_ascii=False))
        else:
            rem = max(0.0, db["limit_usd"] - db["spent_usd"])
            print(
                f"Budget: ${db['spent_usd']:.4f} / ${db['limit_usd']:.2f} "
                f"(remaining ${rem:.4f}, calls={len(db['calls'])}, "
                f"in={db['total_input_tokens']:,}, out={db['total_output_tokens']:,})"
            )
            if db["spent_usd"] >= db["warn_usd"]:
                print("WARNING: spent >= warn threshold!", file=sys.stderr)
    elif a.cmd == "check":
        try:
            db = check_budget(a.file, a.est)
            print(f"OK: ${db['spent_usd']:.4f} + ${a.est:.4f} <= ${db['limit_usd']:.2f}")
        except BudgetExceededError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
