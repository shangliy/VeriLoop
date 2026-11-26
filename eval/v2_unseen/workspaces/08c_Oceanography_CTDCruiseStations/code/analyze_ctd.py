"""Audit cruise_ctd.csv: coverage of CTD variables and station geometry.

Stdlib only (pandas is not installed in this environment). Read-only on data/.
"""
import csv
import math
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "data/cruise_ctd.csv"
CTD_COLS = ["temperature_c", "salinity_psu", "pressure_dbar"]


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


with open(PATH, newline="") as f:
    rows = list(csv.DictReader(f))

print(f"file: {PATH}")
print(f"columns: {list(rows[0].keys())}")
print(f"n_stations: {len(rows)}")

print("\n== CTD variable coverage ==")
total_nonmissing = 0
for col in CTD_COLS:
    vals = [r[col].strip() for r in rows]
    nonmissing = [v for v in vals if v not in ("", "NA", "nan", "NaN")]
    total_nonmissing += len(nonmissing)
    print(f"{col}: non-missing={len(nonmissing)}/{len(rows)}")
print(f"total non-missing CTD values: {total_nonmissing}")
print("profile/thermohaline analysis possible:", total_nonmissing > 0)

print("\n== Station geometry ==")
lats = [float(r["lat"]) for r in rows]
lons = [float(r["lon"]) for r in rows]
print(f"lat range: {min(lats):.4f} to {max(lats):.4f}")
print(f"lon range: {min(lons):.4f} to {max(lons):.4f}")
print("\nstation  lat        lon        nearest_km  nearest_station")
for i, r in enumerate(rows):
    best = None
    for j, s in enumerate(rows):
        if i == j:
            continue
        d = haversine_km(lats[i], lons[i], lats[j], lons[j])
        if best is None or d < best[0]:
            best = (d, s["station_id"])
    print(f"{r['station_id']:<8} {lats[i]:<10.4f} {lons[i]:<10.4f} {best[0]:<11.1f} {best[1]}")

pairs = [
    haversine_km(lats[i], lons[i], lats[j], lons[j])
    for i in range(len(rows))
    for j in range(i + 1, len(rows))
]
print(f"\nmax pairwise station distance: {max(pairs):.1f} km")
print(f"min pairwise station distance: {min(pairs):.1f} km")
