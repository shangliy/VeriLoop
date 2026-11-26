# Microseismic Analysis Brief: Source Clustering and Structural Context

**Scope.** Station geometry (`data/stations.csv`) and P-wave picks (`data/arrival_times.csv`).
**Code.** `code/analysis.py` (run with `python3 -I`). **Log.** `out/analysis_stdout.log`. **Summary.** `outputs/summary.json`.

## Bottom line

1. **No source location or spatial cluster can be established from these data.** Each of the 12 `event_id` values has exactly one pick, from one station. A hypocentre needs origin time plus x, y, z, so at least 4 picks per event are required, plus a velocity model.
2. **The arrival times do not behave like physical P-wave moveout.** They fit a straight clock of 0.5006 s per event with 16 ms residual RMS, and they cycle strictly round-robin through S0 to S4. Physical moveout across this array would be 1.1–2.2 s, so the picks carry no station-dependent travel-time signal. This is a data-provenance concern and should be checked before any interpretation.
3. **Structural context is limited to array geometry.** The array is a 15.8 km² surface footprint with a 233° azimuthal gap as seen from its centroid. No velocity model, geology, faults, or elevation data were supplied, so no structural interpretation is possible beyond the geometry.

## 1. Data inventory and quality control

| Item | Value |
|---|---|
| Stations | 5 (S0–S4), all at z = 0.0 km (surface) |
| Picks | 12 rows, 12 unique `event_id` values |
| Picks per event | **1 for every event** |
| Picks per station | S0: 3, S1: 3, S2: 2, S3: 2, S4: 2 |
| Unknown station IDs / duplicate (event, station) pairs | 0 / 0 |
| Arrival range | −0.0011 s to 5.4902 s; monotone in `event_id` |

The file is internally clean: no missing or duplicated records. The problem is structural. Every event is observed at a single station, so there is no multi-station association.

## 2. Station geometry (structural context)

| Metric | Value |
|---|---|
| x range | 0.212 to 5.109 km |
| y range | 3.042 to 9.623 km |
| Centroid (x, y) | (3.068, 6.472) km |
| Convex-hull area | 15.77 km² (4 hull vertices, so the array is roughly a quadrilateral) |
| Largest aperture | 6.72 km (S2–S3) |
| Smallest spacing | 1.77 km (S0–S1) |
| Azimuths from centroid | 33.3°, 77.7°, 174.0°, 197.3°, 300.8° |
| Largest azimuthal gap | **233.2°** |

The array is elongated NE–SW and sits on one side of its own centroid. The 233° gap means sources outside the footprint, or in the empty sector, would be poorly constrained. Depth resolution would also be weak because all stations are at the surface.

**Structural interpretation.** Nothing beyond the geometry can be concluded. The data contain no velocity model, layering, faults, or station elevation. Any statement about structure would be speculation.

## 3. Temporal structure of the picks

- **Linear trend:** arrival = −0.0063 s + 0.5006 s × `event_id`, residual RMS 0.0160 s, maximum |residual| 0.0368 s.
- **Inter-pick intervals:** mean 0.4992 s, standard deviation 0.0288 s, coefficient of variation (CV) 0.058.
- **Station sequence:** S0, S1, S2, S3, S4, S0, … strictly round-robin.

Taken together, these points show that the picks are almost exactly one event every 0.5 s, assigned to stations in a fixed cycle. Natural microseismicity normally shows bursty or Poisson-like inter-event times, not a CV of 0.058 with a fixed station rotation. **A regular clock-like pattern like this is a red flag for synthetic, resampled, or index-derived timestamps.**

On temporal clustering: the data cannot show clusters in the usual sense. There are no bursts, sequences, or aftershock-like decay to test.

## 4. Moveout and apparent-velocity tests

For each consecutive pair of picks at different stations, I computed the implied speed as inter-station distance divided by time difference. If the picks came from a single source moving across the array, these speeds would be roughly constant.

| Pair | Distance (km) | Δt (s) | Implied speed (km/s) |
|---|---|---|---|
| S0→S1 | 1.773 | 0.505 | 3.51 |
| S1→S2 | 5.517 | 0.483 | 11.42 |
| S2→S3 | 6.719 | 0.483 | 13.92 |
| S3→S4 | 2.301 | 0.535 | 4.30 |
| S4→S0 | 3.087 | 0.493 | 6.26 |

The implied speeds range from 3.5 to 13.9 km/s with a CV of 0.55. There is no consistent value, so **the picks are not a coherent moving source**. Plausible crustal P speeds (about 3–6 km/s) appear only in some pairs.

Expected physical moveout across the array is up to 2.24 s at 3 km/s and 1.12 s at 6 km/s over the 6.72 km maximum aperture. The observed pick scatter is 0.016 s, and the station-mean residuals are all below 16 ms in magnitude. The picks therefore show almost no station-dependent travel-time structure.

## 5. Source-location feasibility tests

I ran two grid searches over a velocity range of 2–7 km/s, a horizontal range of −2 to 8 km (x) and 0 to 12 km (y), and a depth range of 0.5 to 12 km. For each grid point, origin time was solved by least squares.

- **[A] One common source for all 12 picks:** best RMS residual 1.72 s, at (4.25, 3.25, 0.5) km with v = 7.0 km/s. This is about 100 times the 16 ms pick scatter, so **no single source is consistent with the data**.
- **[B] One source from the first pick at each station (5 picks):** best RMS 0.41 s. This solution sits on the edge of the search box (x = −2 km, v = 2.0 km/s, z = 8.5 km). It has 1 degree of freedom after the velocity search, so it is not a credible location.

Neither test supports a source location. Per-event location is impossible with one pick per event.

## 6. Answers to the brief's questions

**Source clustering.** Not determinable. Each event has one pick, so no spatial clustering or hypocentre can be estimated. The only regularity is temporal: a 0.5 s clock with a CV of 0.058, which is unusual for natural microseismicity and suggests a provenance problem.

**Structural context.** Only the array geometry is available: a 15.8 km² footprint, 6.7 km maximum aperture, and a 233° azimuthal gap. There is no velocity or structural model to support any geological interpretation.

## 7. Limitations

- Twelve picks from five surface stations are far too few for any statistical clustering analysis.
- The velocity model is unknown. The velocity search in the grid tests is a sensitivity check, not an inversion.
- Station depths are all 0.0 km, so the array cannot constrain depth beyond the grid search.
- Only P picks are given. No S picks, pick uncertainties, or waveforms are available.
- The correlation between station residual and distance from centroid (r = −0.57, n = 5) is not significant and is not interpreted.
- No figures were produced: the environment's matplotlib installation failed (missing PIL). Results are presented as tables.

## 8. Recommended next steps

1. **Verify the provenance of `arrival_s`.** Check whether these values were generated by a clock or index rather than picked from waveforms. Pick times should be reported with waveform and event IDs.
2. **Obtain multi-station associations.** Each event should have at least 4 P picks (more is better), ideally with S picks as well, plus pick uncertainties.
3. **Obtain a velocity model and station elevations** before any location or structural interpretation.
4. **Re-run this analysis** once the event-station association is available. The location code in `code/analysis.py` can then be used with a proper origin-time and hypocentre inversion.

## Reproducibility

- Run: `python3 -I code/analysis.py > out/analysis_stdout.log`
- Outputs: `outputs/summary.json`, `out/analysis_stdout.log`
- Dependencies: NumPy (no other scientific dependencies are needed for this analysis)
