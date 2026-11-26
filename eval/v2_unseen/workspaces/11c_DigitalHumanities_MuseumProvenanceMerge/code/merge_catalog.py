#!/usr/bin/env python3
"""Merge museum_export_a.csv and museum_export_b.csv into one deduplicated catalog
and summarise how the collection is distributed over time.

Run:  python3 -I code/merge_catalog.py   (from the workspace root)
Writes: outputs/catalog.csv, outputs/id_crosswalk.csv, outputs/time_distribution.csv
Prints the audit log to stdout (captured into out/merge_log.txt).
"""
import csv
import os
import re
import collections

BASE = "/home/shawnyang/Documents/VeriLoop/eval/v2_unseen/workspaces/11c_DigitalHumanities_MuseumProvenanceMerge"
SOURCES = {
    "A": os.path.join(BASE, "data", "museum_export_a.csv"),
    "B": os.path.join(BASE, "data", "museum_export_b.csv"),
}
OUT_DIR = os.path.join(BASE, "outputs")

# ---------------------------------------------------------------------------
# Accession normalisation.
# Strip whitespace, hyphens and underscores, upper-case, drop leading zeros in
# the numeric part (T088 -> T88, A-001 -> A1, Y-050 -> Y50). Keep any trailing
# letters (T88X stays distinct from T88). Non-ID rows (blank, '---', TOTAL_ROWS,
# EXPORT_NOTE, FOOTER) return None.
# ---------------------------------------------------------------------------
def canon(raw):
    s = re.sub(r"[\s_\-]", "", raw.strip().upper())
    m = re.fullmatch(r"([A-Z]+)(\d+)([A-Z]*)", s)
    if not m:
        return None
    return f"{m.group(1)}{int(m.group(2))}{m.group(3)}"


# ---------------------------------------------------------------------------
# Dating decisions, one per canonical ID, made by reading the free-text notes
# of every source row for that object. Years: BCE negative, CE positive.
# (representative year, low, high, basis, confidence, is_reproduction)
# Representative year = the explicit date where one exists, otherwise the
# midpoint of the admissible range.
# ---------------------------------------------------------------------------
DATING = {
    "X100": (-200, -206, 220, "Card '200BC'; Han-style vase (Han 206 BCE-220 CE)", "high", False),
    "M205": (1752, 1752, 1752, "Ledger date 1752; '18th c' and 'mid-1700s' are consistent", "high", False),
    "T88": (762, 618, 907, "Card: Tang 618-907", "high", False),
    "T88X": (None, None, None, "No date in source", "none", False),
    "P401": (1900, 1890, 1910, "Card 'circa 1890-1910'; 'late 19th c'", "high", False),
    "K12": (550, 550, 550, "Label '550 CE approx'; A-side 'Northern Qi style; year unclear'", "medium", False),
    "R500": (1203, 1127, 1279, "'Song' narrowed by 'Southern Song period' note", "medium", False),
    "D77": (1650, 1603, 1700, "Edo (1603-1868) intersect '17th c'", "high", False),
    "N300": (1596, 1572, 1620, "Wanli reign (1572-1620) intersect 'late Ming'", "medium", False),
    "B44": (1692, 1662, 1722, "Kangxi reign (1662-1722)", "high", False),
    "C901": (1925, 1920, 1929, "'1920s' (B) within 'early 20th c' / Republic era (A)", "high", False),
    "H222": (1150, 1101, 1200, "'12th c' / '12th century'", "high", False),
    "J150": (1850, 1800, 1899, "'19th c' / '1800s'", "high", False),
    "L600": (1765, 1736, 1795, "Qianlong reign (1736-1795); style-based", "medium", False),
    "G333": (-348, -475, -221, "Warring States style (475-221 BCE); 'Zhou period ref'; style-based", "low", False),
    "F888": (1875, 1850, 1899, "'19th c export' intersect 'late Qing' (1850-1912)", "medium", False),
    "A1": (1950, 1901, 2000, "'20th c copy of stele' / 'modern'; date is that of the copy", "high", True),
    "Z999": (1998, 1998, 1998, "Marked reproduction dated 1998", "high", True),
    "S400": (1880, 1880, 1880, "'1880' (B); 'late 19th' consistent", "high", False),
    "W700": (1450, 1400, 1499, "'Ming; 15th c' / '1400s'", "high", False),
    "Y50": (7, -206, 220, "'Han'; reference range 206 BCE-220 CE, no closer date", "medium", False),
    "Q120": (-310, -400, -221, "'Warring States' intersect '400-200 BCE'", "medium", False),
    "V303": (762, 618, 907, "'Tang' / '618-907'", "high", False),
    "U808": (933, 907, 960, "Five Dynasties (907-960) intersect '10th c'", "medium", False),
    "E505": (1850, 1800, 1899, "'19th c' / '1800s'", "high", False),
}

FLAGS = {
    "T88X": "Possible duplicate of T88 (ID typo; B remark 'should match T88'). NOT merged; needs registrar confirmation.",
    "A1": "Reproduction: 20th c copy of a stele. Excluded from originals-only distribution.",
    "Z999": "Modern reproduction. Excluded from originals-only distribution.",
    "G333": "Style-based date only.",
    "L600": "Style-based date (Qianlong style).",
    "K12": "Approximate label date (550 CE approx).",
    "M205": "B remark '1752 vs 18th c conflict' is not a real conflict: 1752 lies in the 18th c.",
}


def ordinal(n):
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def century_key(year):
    """Map a year to a signed century index: -2 = 2nd c. BCE, +19 = 19th c. CE."""
    if year < 0:
        return -((abs(year) + 99) // 100)
    return (year + 99) // 100


def century_label(k):
    return f"{ordinal(abs(k))} c. {'BCE' if k < 0 else 'CE'}"


def century_interval(k):
    if k < 0:
        n = -k
        return (-100 * n, -100 * (n - 1) - 1)
    return (100 * (k - 1) + 1, 100 * k)


def load_rows():
    rows, excluded = [], []
    for src, path in SOURCES.items():
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader)
            for row in reader:
                line = reader.line_num
                row = (row + ["", "", ""])[:3]
                raw, name, note = row
                if not any(c.strip() for c in row):
                    excluded.append((src, line, "blank row", raw, name, note))
                    continue
                key = canon(raw) if raw.strip() else None
                if key is None:
                    excluded.append((src, line, "non-object row (header/footer/blank ID)", raw, name, note))
                    continue
                rows.append(dict(src=src, line=line, raw=raw.strip(), key=key,
                                 name=name.strip(), note=note.strip(), header=header))
    return rows, excluded


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows, excluded = load_rows()

    print("== Input ==")
    for src in SOURCES:
        n_valid = sum(1 for r in rows if r["src"] == src)
        n_excl = sum(1 for e in excluded if e[0] == src)
        print(f"Batch {src}: {n_valid} object rows kept, {n_excl} non-object rows excluded")
    for e in excluded:
        print(f"  excluded {e[0]} line {e[1]}: {e[2]} | raw='{e[3]}' name='{e[4]}' note='{e[5]}'")
    print(f"Total object rows: {len(rows)}")

    # naive baselines
    naive_exact = len({r["raw"] for r in rows})
    naive_exact_untrimmed = len({r["raw"] for r in rows})
    print(f"\n== Naive dedup baseline ==")
    print(f"Distinct raw accession strings (whitespace-trimmed): {naive_exact}")

    groups = collections.defaultdict(list)
    for r in rows:
        groups[r["key"]].append(r)
    missing = [k for k in groups if k not in DATING]
    assert not missing, f"no dating decision for {missing}"

    print(f"\n== Normalised dedup ==")
    print(f"Distinct canonical IDs (catalog records): {len(groups)}")
    both = [k for k, g in groups.items() if {r['src'] for r in g} == {"A", "B"}]
    a_only = [k for k, g in groups.items() if {r['src'] for r in g} == {"A"}]
    b_only = [k for k, g in groups.items() if {r['src'] for r in g} == {"B"}]
    print(f"In both batches: {len(both)} -> {sorted(both)}")
    print(f"Batch A only: {len(a_only)} -> {sorted(a_only)}")
    print(f"Batch B only: {len(b_only)} -> {sorted(b_only)}")
    for src in SOURCES:
        n_src = sum(1 for r in rows if r["src"] == src)
        n_grp = sum(1 for g in groups.values() if any(r["src"] == src for r in g))
        print(f"Batch {src}: {n_src} rows -> {n_grp} objects; {n_src - n_grp} within-batch duplicate rows")
    print(f"Rows removed by merge: {len(rows) - len(groups)} of {len(rows)}")
    print("Cross-variant keys (raw IDs that differ but map to the same object):")
    for k, g in sorted(groups.items()):
        variants = sorted({r["raw"] for r in g})
        if len(variants) > 1:
            print(f"  {k}: {variants}")

    # Build catalog records
    recs = []
    for k, g in groups.items():
        g_sorted = sorted(g, key=lambda r: (r["src"], r["line"]))
        a_rows = [r for r in g_sorted if r["src"] == "A"]
        title = (a_rows[0] if a_rows else g_sorted[0])["name"]
        rep, lo, hi, basis, conf, repro = DATING[k]
        recs.append(dict(
            catalog_id=k,
            title=title,
            sources="+".join(sorted({r["src"] for r in g})),
            n_rows_A=sum(1 for r in g if r["src"] == "A"),
            n_rows_B=sum(1 for r in g if r["src"] == "B"),
            raw_variants="; ".join(sorted({r["raw"] for r in g})),
            date_representative=rep if rep is not None else "",
            date_low=lo if lo is not None else "",
            date_high=hi if hi is not None else "",
            century=century_label(century_key(rep)) if rep is not None else "undated",
            dating_basis=basis,
            date_confidence=conf,
            is_reproduction=repro,
            flags=FLAGS.get(k, ""),
            source_notes=" | ".join(f"{r['src']}:{r['note']}" for r in g_sorted),
            _rep=rep, _lo=lo, _hi=hi,
        ))
    recs.sort(key=lambda r: (r["_rep"] is None, r["_rep"] if r["_rep"] is not None else 0))

    cat_fields = ["catalog_id", "title", "sources", "n_rows_A", "n_rows_B", "raw_variants",
                  "date_representative", "date_low", "date_high", "century", "dating_basis",
                  "date_confidence", "is_reproduction", "flags", "source_notes"]
    with open(os.path.join(OUT_DIR, "catalog.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cat_fields, extrasaction="ignore")
        w.writeheader()
        for r in recs:
            w.writerow(r)

    with open(os.path.join(OUT_DIR, "id_crosswalk.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["batch", "line", "raw_id", "canonical_id", "object_name", "note"])
        for r in sorted(rows, key=lambda r: (r["src"], r["line"])):
            w.writerow([r["src"], r["line"], r["raw"], r["key"], r["name"], r["note"]])

    # Time distribution
    dated = [r for r in recs if r["_rep"] is not None]
    undated = [r for r in recs if r["_rep"] is None]
    originals = [r for r in dated if not r["is_reproduction"]]
    print(f"\n== Dating ==")
    print(f"Dated records: {len(dated)}; undated: {len(undated)} ({[r['catalog_id'] for r in undated]})")
    print(f"Reproductions among dated: {len(dated) - len(originals)} "
          f"({[r['catalog_id'] for r in dated if r['is_reproduction']]})")
    print(f"Date confidence (all records): " +
          str(collections.Counter(r["date_confidence"] for r in recs)))

    ks = sorted(set(century_key(r["_rep"]) for r in dated) | set(range(-4, 0)) | set(range(1, 21)))
    ks = [k for k in ks if -4 <= k <= 20]
    rows_out = []
    print("\nCentury  | midpoint(all) | midpoint(originals) | range-overlap(all) | IDs (midpoint)")
    for k in ks:
        s, e = century_interval(k)
        m_all = [r for r in dated if century_key(r["_rep"]) == k]
        m_orig = [r for r in m_all if not r["is_reproduction"]]
        overl = [r for r in dated if r["_lo"] <= e and r["_hi"] >= s]
        ids = ",".join(r["catalog_id"] for r in m_all)
        rows_out.append([century_label(k), len(m_all), len(m_orig), len(overl), ids])
        print(f"{century_label(k):<9}| {len(m_all):>13} | {len(m_orig):>19} | {len(overl):>18} | {ids}")
    with open(os.path.join(OUT_DIR, "time_distribution.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["century", "n_midpoint_all", "n_midpoint_originals", "n_range_overlap_all", "catalog_ids_midpoint"])
        w.writerows(rows_out)
    print(f"\nundated (not placed on timeline): {len(undated)}")
    pre220 = [r for r in originals if r["_rep"] < 220]
    print(f"Originals dated before 220 CE (midpoint): {len(pre220)}")
    c19 = [r for r in originals if century_key(r["_rep"]) == 19]
    print(f"Originals in 19th c (midpoint): {len(c19)} of {len(originals)} dated originals")
    before1600 = [r for r in originals if r["_rep"] < 1600]
    print(f"Originals before 1600 (midpoint): {len(before1600)}; from 1600 on: {len(originals) - len(before1600)}")


if __name__ == "__main__":
    main()
