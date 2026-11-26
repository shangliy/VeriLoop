#!/usr/bin/env python3
"""Inspect the supplied CSV without modifying it."""
import csv
import hashlib
from pathlib import Path

path = Path('data/sensor_panel_timeseries.csv')
raw = path.read_bytes()
print(f'File: {path}')
print(f'File size (bytes): {len(raw)}')
print(f'SHA-256: {hashlib.sha256(raw).hexdigest()}')
with path.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    print(f'Columns ({len(reader.fieldnames or [])}): {", ".join(reader.fieldnames or [])}')
    rows = list(reader)
print(f'Data rows: {len(rows)}')
print(f'Nonblank asset identifiers: {len({r["asset_id"] for r in rows if r.get("asset_id")})}')
print(f'Nonblank timestamps: {sum(bool(r.get("timestamp_utc")) for r in rows)}')
if not rows:
    print('Observation window: unavailable; no observation rows')
    print('Sampling interval: unavailable; no observation rows')
    print('Trends, comparisons, relationships, and asset risk ranking: unavailable; no observation rows')
