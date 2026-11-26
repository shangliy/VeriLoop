"""Reconcile WMS export A (wms_alpha.csv) against WMS export B (wms_beta.csv).

Stdlib only. Reads from data/ (read-only), writes to out/.
Assumptions (made explicit, and stress-tested in the sensitivity table):
  * SKU keys are compared case-/whitespace-insensitively.
  * Warehouse codes: A uses 'WH1'; B uses 'Warehouse-01'. Mapped WH1 <-> Warehouse-01
    (the only warehouse code in each file; the mapping is an assumption, not documented).
  * A timestamps are UTC (explicit '+00' suffix).
  * B timestamps are 'local' with no offset. Base case assumes UTC+0; the sensitivity
    table shows which offsets keep the same calendar-day match.
  * Matching grain = (SKU, warehouse, UTC calendar date). Quantities are snapshots, so
    a daily snapshot comparison is the only defensible join.
"""
import csv
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "out")
os.makedirs(OUT, exist_ok=True)

WH_MAP = {"WH1": "WH1", "WAREHOUSE-01": "WH1"}  # canonical warehouse id
BASE_OFFSET_HOURS = 0  # B local -> UTC offset assumed in base case


def norm_sku(s):
    return s.strip().upper()


def norm_wh(s):
    return WH_MAP.get(s.strip().upper(), s.strip().upper())


def parse_a(ts):
    # e.g. '2026-03-01 00:00:00+00'
    s = ts.strip()
    # Export uses a bare hour offset ('+00'); normalize to '+00:00' for strptime %z.
    if len(s) >= 3 and s[-3] in "+-" and s[-2:].isdigit():
        s = s + ":00"
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def parse_b(ts, offset_hours):
    # e.g. '2026-03-01 08:00:00' local; local = UTC + offset
    naive = datetime.strptime(ts.strip(), "%Y-%m-%d %H:%M:%S")
    return (naive - timedelta(hours=offset_hours)).replace(tzinfo=timezone.utc)


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_a():
    rows = []
    for r in load(os.path.join(DATA, "wms_alpha.csv")):
        ts = parse_a(r["as_of_utc"])
        rows.append({
            "sku": norm_sku(r["sku"]),
            "wh": norm_wh(r["warehouse"]),
            "wh_raw": r["warehouse"],
            "ts_utc": ts,
            "date": ts.date().isoformat(),
            "qty": float(r["qty"]),
            "src_row": r,
        })
    return rows


def load_b(offset_hours=BASE_OFFSET_HOURS):
    rows = []
    for r in load(os.path.join(DATA, "wms_beta.csv")):
        ts = parse_b(r["timestamp_local"], offset_hours)
        rows.append({
            "sku": norm_sku(r["SKU"]),
            "wh": norm_wh(r["Site"]),
            "wh_raw": r["Site"],
            "ts_utc": ts,
            "date": ts.date().isoformat(),
            "qty": float(r["Quantity"]),
            "src_row": r,
        })
    return rows


def reconcile(a_rows, b_rows):
    """Match on (sku, wh, utc date). Duplicates on a key are reported, not silently collapsed."""
    a_idx, b_idx = defaultdict(list), defaultdict(list)
    for r in a_rows:
        a_idx[(r["sku"], r["wh"], r["date"])].append(r)
    for r in b_rows:
        b_idx[(r["sku"], r["wh"], r["date"])].append(r)
    keys = sorted(set(a_idx) | set(b_idx))
    results = []
    for k in keys:
        a_list, b_list = a_idx.get(k, []), b_idx.get(k, [])
        if a_list and b_list:
            status = "matched" if len(a_list) == 1 and len(b_list) == 1 else "duplicate_key"
            a_q = sum(x["qty"] for x in a_list)
            b_q = sum(x["qty"] for x in b_list)
            diff = a_q - b_q
            status_qty = "match" if abs(diff) < 1e-9 else "qty_mismatch"
        elif a_list:
            status, a_q, b_q, diff, status_qty = "only_in_A", sum(x["qty"] for x in a_list), None, None, "n/a"
        else:
            status, a_q, b_q, diff, status_qty = "only_in_B", None, sum(x["qty"] for x in b_list), None, "n/a"
        results.append({
            "sku": k[0], "wh": k[1], "utc_date": k[2],
            "qty_A": a_q, "qty_B": b_q, "qty_diff_A_minus_B": diff,
            "key_status": status, "qty_status": status_qty,
        })
    return results


def kpis(a_rows, b_rows, results):
    n_a, n_b = len(a_rows), len(b_rows)
    matched = [r for r in results if r["key_status"] == "matched"]
    mism = [r for r in matched if r["qty_status"] == "qty_mismatch"]
    only_a = [r for r in results if r["key_status"] == "only_in_A"]
    only_b = [r for r in results if r["key_status"] == "only_in_B"]
    return {
        "rows_A": n_a,
        "rows_B": n_b,
        "distinct_skus_A": len({r["sku"] for r in a_rows}),
        "distinct_skus_B": len({r["sku"] for r in b_rows}),
        "distinct_warehouses_A": sorted({r["wh"] for r in a_rows}),
        "distinct_warehouses_B": sorted({r["wh"] for r in b_rows}),
        "keys_total": len(results),
        "matched_keys": len(matched),
        "match_rate_of_A_keys": round(len(matched) / max(1, len({(r["sku"], r["wh"], r["utc_date"]) for r in results if r["qty_A"] is not None})), 4),
        "coverage_of_B_keys": round(len(matched) / max(1, n_b), 4),
        "only_in_A": len(only_a),
        "only_in_B": len(only_b),
        "qty_mismatches_on_matched": len(mism),
        "qty_accuracy_on_matched": round((len(matched) - len(mism)) / max(1, len(matched)), 4),
        "units_matched_A": sum(r["qty_A"] for r in matched),
        "units_matched_B": sum(r["qty_B"] for r in matched),
        "units_only_in_A": sum(r["qty_A"] for r in only_a),
        "units_only_in_B": sum(r["qty_B"] for r in only_b),
        "A_snapshot_dates": sorted({r["date"] for r in a_rows}),
        "B_snapshot_dates_base_case": sorted({r["date"] for r in b_rows}),
    }


def sensitivity():
    """Which B local->UTC offsets (hours) keep the base-case match, and which status results."""
    a_rows = load_a()
    out = []
    for off in range(-12, 15):
        b_rows = load_b(off)
        res = reconcile(a_rows, b_rows)
        counts = defaultdict(int)
        for r in res:
            counts[r["key_status"]] += 1
        out.append({
            "B_offset_hours": off,
            "B_utc_timestamp": b_rows[0]["ts_utc"].isoformat(),
            "matched": counts["matched"],
            "only_in_A": counts["only_in_A"],
            "only_in_B": counts["only_in_B"],
            "duplicate_key": counts["duplicate_key"],
        })
    return out


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    a_rows, b_rows = load_a(), load_b()
    results = reconcile(a_rows, b_rows)
    k = kpis(a_rows, b_rows, results)
    sens = sensitivity()

    write_csv(os.path.join(OUT, "recon_detail.csv"), results)
    write_csv(os.path.join(OUT, "sensitivity_offset.csv"), sens)
    with open(os.path.join(OUT, "kpis.json"), "w", encoding="utf-8") as f:
        json.dump(k, f, indent=2, default=str)

    print("== Parsed A rows ==")
    for r in a_rows:
        print(r["src_row"], "->", r["sku"], r["wh"], r["ts_utc"].isoformat(), r["qty"])
    print("== Parsed B rows (base offset %+d h) ==" % BASE_OFFSET_HOURS)
    for r in b_rows:
        print(r["src_row"], "->", r["sku"], r["wh"], r["ts_utc"].isoformat(), r["qty"])
    print("== Reconciliation detail ==")
    for r in results:
        print(r)
    print("== KPIs ==")
    print(json.dumps(k, indent=2, default=str))
    print("== Sensitivity to B timezone offset ==")
    for s in sens:
        print(s)


if __name__ == "__main__":
    main()
