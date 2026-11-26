# CTD Vertical Profile and Thermohaline Structure: Cruise Station Report

## Summary

The vertical profile and thermohaline analysis could not be carried out. `data/cruise_ctd.csv` contains station positions for six CTD stations (ST0–ST5), but **every CTD measurement column is empty**: `temperature_c`, `salinity_psu`, and `pressure_dbar` have 0 non-missing values out of 6 rows. There are no depth profiles, no temperature or salinity values, and no water-mass or stratification information to analyze. Rather than fabricate values, this report documents the data state, the station geometry that is available, and what is needed to proceed.

## Data

- **File:** `data/cruise_ctd.csv` (read-only; not modified)
- **Rows:** 6 stations
- **Columns:** `station_id`, `lat`, `lon`, `temperature_c`, `salinity_psu`, `pressure_dbar`

| Variable | Non-missing / 6 |
|---|---|
| `lat`, `lon`, `station_id` | 6 / 6 |
| `temperature_c` | 0 / 6 |
| `salinity_psu` | 0 / 6 |
| `pressure_dbar` | 0 / 6 |

Source: `out/analyze_ctd_stdout.log`, produced by `code/analyze_ctd.py`.

## Methods

`code/analyze_ctd.py` is a stdlib-only audit script (`pandas` is not installed here). It:

1. Counts non-missing values in each CTD column.
2. Reports the geographic extent of the stations.
3. Computes great-circle (haversine) distances between stations, including each station's nearest neighbor.

It does not interpolate, derive, or impute any CTD quantity, because none exist in the input.

## Results

### CTD coverage

No CTD variable has any non-missing value. The check `profile/thermohaline analysis possible` returns `False`.

### Station geometry

- Latitude range: −19.9328° to −18.2354°
- Longitude range: 40.3282° to 41.9837°
- Nearest-neighbor distances range from 47.9 km (ST0–ST1) to 114.7 km (ST5 to ST4).
- Maximum pairwise distance: 204.6 km. Minimum pairwise distance: 47.9 km.

| Station | Lat | Lon | Nearest station | Distance (km) |
|---|---|---|---|---|
| ST0 | −19.7649 | 41.4093 | ST1 | 47.9 |
| ST1 | −19.9328 | 40.9874 | ST0 | 47.9 |
| ST2 | −18.3183 | 41.8248 | ST3 | 86.0 |
| ST3 | −19.0772 | 41.9837 | ST2 | 86.0 |
| ST4 | −19.2527 | 40.5070 | ST1 | 90.8 |
| ST5 | −18.2354 | 40.3282 | ST4 | 114.7 |

The stations form a sparse, roughly 200 km-scale array in the southwestern Indian Ocean (Mozambique Channel region, inferred from coordinates). Stations are arranged in two loose clusters: an eastern pair (ST2, ST3) near 42°E and a western group (ST1, ST4, ST5) near 40.3–41°E, with ST0 in between. The coordinates alone do not establish the region's oceanography; that inference is not supported by any CTD measurement here.

## Discussion

Without temperature, salinity, or pressure, none of the requested analyses can be performed:

- **Vertical profiles** (T and S versus depth, mixed-layer depth, thermocline depth) require pressure-indexed casts.
- **Thermohaline structure** (T–S diagrams, water-mass identification, stability via Brunt–Väisälä frequency) requires paired T and S values.
- **Horizontal structure** across the array (front or eddy detection) requires CTD values at each station, not only positions.

The station geometry is useful for planning but is not a substitute for these data. Any statement about water masses, stratification, or fronts in this region would be unsupported by this file.

## Limitations

- The file has no measurements, so this report contains no oceanographic result.
- The regional attribution (Mozambique Channel) is inferred from coordinates only and is not verified against any metadata.
- No cast timestamps, instrument metadata, depth bins, or QC flags are present.

## Recommendations

To complete the analysis, the following are needed:

1. A CTD data export with per-cast pressure (or depth) and paired temperature and salinity values for each station, in long format (`station_id, pressure_dbar, temperature_c, salinity_psu`), or one row per sample.
2. Cast timestamps and instrument/calibration metadata, so that salinity can be checked for conductivity-calibration issues and so profiles can be placed in time.
3. Any QC flags from the data provider.

Once the profile data are supplied, the same workflow can produce T/S/density profiles per station, a T–S diagram, mixed-layer and thermocline depths, and a stability profile. `code/analyze_ctd.py` should then be extended to load and validate those columns before computing any derived quantity.

## Files

- `code/analyze_ctd.py`: coverage and geometry audit (stdlib only)
- `out/analyze_ctd_stdout.log`: stdout of the audit run
- `report/report.md`: this report
- `report/ctd_report.md`: copy of this report under the requested deliverable name
