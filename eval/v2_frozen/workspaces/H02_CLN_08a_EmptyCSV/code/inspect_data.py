"""Feasibility check for data/sensor_panel_timeseries.csv.

Reads the file read-only, reports byte size, line count, header, and the
number of data rows, and checks whether the columns needed for the requested
analysis (timestamps, asset_id, zone, vibration, bearing temperature, rpm,
load) are present with at least one data row. Writes nothing except stdout.
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PATH = os.path.join(ROOT, "data", "sensor_panel_timeseries.csv")

REQUIRED = [
    "timestamp_utc", "asset_id", "zone", "vibration_rms_mm_s",
    "peak_accel_g", "bearing_temp_c", "rpm", "load_pct", "quality_flag",
]

print(f"file: {os.path.relpath(PATH, ROOT)}")
print(f"exists: {os.path.isfile(PATH)}")
size = os.path.getsize(PATH)
print(f"size_bytes: {size}")

with open(PATH, "rb") as fh:
    raw = fh.read()
print(f"raw_newline_count: {raw.count(b'\n')}")
print(f"ends_with_newline: {raw.endswith(b'\n')}")

with open(PATH, newline="", encoding="utf-8") as fh:
    rows = list(csv.reader(fh))

header = rows[0] if rows else []
data_rows = [r for r in rows[1:] if any(cell.strip() for cell in r)]
print(f"header_fields: {len(header)}")
print(f"header: {header}")
print(f"data_rows: {len(data_rows)}")

missing = [c for c in REQUIRED if c not in header]
print(f"missing_required_columns: {missing}")

if len(data_rows) == 0:
    print("FEASIBILITY: INFEASIBLE - header only, no observations; no window, "
          "assets, sampling, trends, or cross-variable relationships can be computed.")
    sys.exit(0)

print("FEASIBILITY: data rows present; analysis could proceed.")
