"""Microseismic QC + sensitivity analysis for stations.csv / arrival_times.csv.

Outputs (stdout is captured to out/analysis_stdout.log; JSON summary to outputs/summary.json).
"""
import csv
import json
import math
import os
import itertools
import numpy as np

ROOT = "/home/shawnyang/Documents/VeriLoop/eval/v2_unseen/workspaces/10b_Geophysics_MicroseismicBrief"
DATA = os.path.join(ROOT, "data")
OUTD = os.path.join(ROOT, "outputs")
os.makedirs(OUTD, exist_ok=True)

summary = {}

# ---------------------------------------------------------------- load
with open(os.path.join(DATA, "stations.csv"), newline="") as f:
    st_rows = list(csv.DictReader(f))
with open(os.path.join(DATA, "arrival_times.csv"), newline="") as f:
    pk_rows = list(csv.DictReader(f))

stations = {r["station_id"]: np.array([float(r["x_km"]), float(r["y_km"]), float(r["z_km"])]) for r in st_rows}
sta_ids = list(stations.keys())
ev = np.array([int(r["event_id"]) for r in pk_rows])
sid = [r["station_id"] for r in pk_rows]
t = np.array([float(r["arrival_s"]) for r in pk_rows])
order = np.argsort(t)

print("=== 1. Data inventory ===")
print(f"stations: {len(stations)} rows, ids={sta_ids}")
print(f"picks: {len(pk_rows)} rows, unique event_ids={len(set(ev.tolist()))}")
print(f"picks per event_id: {dict(zip(*np.unique(ev, return_counts=True)))}")
counts = {s: sid.count(s) for s in sta_ids}
print(f"picks per station: {counts}")
print(f"unknown station ids in picks: {set(sid) - set(sta_ids)}")
print(f"duplicate (event,station) pairs: {len(pk_rows) - len(set(zip(ev.tolist(), sid)))}")
print(f"arrival range (s): [{t.min():.4f}, {t.max():.4f}]; monotone in event_id: {bool(np.all(np.diff(t) > 0))}")
summary["n_stations"] = len(stations)
summary["n_picks"] = len(pk_rows)
summary["picks_per_event_max"] = int(np.max(np.unique(ev, return_counts=True)[1]))
summary["picks_per_station"] = counts

# ---------------------------------------------------------------- geometry
print("\n=== 2. Station geometry ===")
xy = np.array([stations[s][:2] for s in sta_ids])
zs = np.array([stations[s][2] for s in sta_ids])
print(f"x range: {xy[:,0].min():.3f} to {xy[:,0].max():.3f} km; y range: {xy[:,1].min():.3f} to {xy[:,1].max():.3f} km")
print(f"station depths (z_km): {sorted(set(zs.tolist()))}")
cen = xy.mean(axis=0)
print(f"centroid (x,y): ({cen[0]:.3f}, {cen[1]:.3f}) km")
pair_d = [(a, b, float(np.linalg.norm(stations[a][:2] - stations[b][:2])))
          for a, b in itertools.combinations(sta_ids, 2)]
dmax = max(pair_d, key=lambda p: p[2])
dmin = min(pair_d, key=lambda p: p[2])
print(f"max inter-station distance: {dmax[0]}-{dmax[1]} = {dmax[2]:.3f} km")
print(f"min inter-station distance: {dmin[0]}-{dmin[1]} = {dmin[2]:.3f} km")
# convex hull area (monotone chain) for array footprint
def hull(points):
    pts = sorted(map(tuple, points))
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]
H = hull(xy)
area = 0.5 * abs(sum(H[i][0]*H[(i+1) % len(H)][1] - H[(i+1) % len(H)][0]*H[i][1] for i in range(len(H))))
print(f"array convex-hull area: {area:.3f} km^2 (hull vertices: {len(H)})")
# azimuthal coverage from centroid
az = [math.degrees(math.atan2(p[1]-cen[1], p[0]-cen[0])) % 360 for p in xy]
gaps = np.diff(sorted(az + [az[0] + 360]))
print(f"azimuths from centroid (deg): {[round(a,1) for a in sorted(az)]}; max azimuthal gap: {gaps.max():.1f} deg")
summary["array_hull_area_km2"] = area
summary["max_station_gap_deg"] = float(gaps.max())
summary["max_pair_distance_km"] = dmax[2]
summary["min_pair_distance_km"] = dmin[2]

# ---------------------------------------------------------------- temporal structure
print("\n=== 3. Temporal structure of picks ===")
A = np.vstack([np.ones_like(ev, dtype=float), ev.astype(float)]).T
coef, *_ = np.linalg.lstsq(A, t, rcond=None)
resid_lin = t - A @ coef
print(f"linear fit arrival = a + b*event_id: a={coef[0]:.4f} s, b={coef[1]:.4f} s/event; residual RMS={np.sqrt(np.mean(resid_lin**2)):.4f} s, max |res|={np.max(np.abs(resid_lin)):.4f} s")
dt = np.diff(t)
print(f"inter-pick intervals: mean={dt.mean():.4f} s, std={dt.std(ddof=1):.4f} s, CV={dt.std(ddof=1)/dt.mean():.4f}")
summary["linear_slope_s_per_event"] = float(coef[1])
summary["linear_resid_rms_s"] = float(np.sqrt(np.mean(resid_lin**2)))
summary["interpick_cv"] = float(dt.std(ddof=1)/dt.mean())

# station cycling pattern
cyc = [sta_ids[i % len(sta_ids)] for i in range(len(ev))]
print(f"station sequence matches strict round-robin S0..S4 repeating: {sid == cyc}")
summary["round_robin"] = sid == cyc

# ---------------------------------------------------------------- moveout test
print("\n=== 4. Moveout / apparent-velocity test (consecutive picks) ===")
app_v = []
for i in range(len(pk_rows)-1):
    a, b = sid[i], sid[i+1]
    if a == b:
        continue
    d = float(np.linalg.norm(stations[a][:2] - stations[b][:2]))
    dtt = t[i+1] - t[i]
    app_v.append(d/dtt)
    print(f"  {a}->{b}: distance={d:.3f} km, dt={dtt:.4f} s, implied speed={d/dtt:.2f} km/s")
app_v = np.array(app_v)
print(f"implied speeds: min={app_v.min():.2f}, median={np.median(app_v):.2f}, max={app_v.max():.2f} km/s; CV={app_v.std(ddof=1)/app_v.mean():.3f}")
summary["implied_speed_range_km_s"] = [float(app_v.min()), float(app_v.max())]

# station-specific residual vs linear trend (station travel-time terms)
print("\n=== 5. Station terms relative to linear trend ===")
st_res = {}
for s in sta_ids:
    m = np.array([x == s for x in sid])
    st_res[s] = float(resid_lin[m].mean())
    print(f"  {s}: mean residual={st_res[s]:+.4f} s, n={m.sum()}")
# correlation of station mean residual with distance from centroid (5 points only; illustrative)
r_d = np.array([np.linalg.norm(stations[s][:2]-cen) for s in sta_ids])
r_m = np.array([st_res[s] for s in sta_ids])
r_c = float(np.corrcoef(r_d, r_m)[0, 1]) if r_m.std() > 0 else float("nan")
print(f"Pearson r(station distance from centroid, station mean residual) = {r_c:.3f} (n=5, not significant)")
summary["station_mean_residuals_s"] = st_res

# ---------------------------------------------------------------- location feasibility
print("\n=== 6. Location feasibility ===")
print("Each event_id has exactly one pick; a hypocentre needs x,y,z and origin time (4 unknowns) => >=4 picks per event.")
print("Picks per event:", int(np.max(np.unique(ev, return_counts=True)[1])), "(max)")

# single-source grid test using all 12 picks (one common origin)
def fit_single_source(idx, vgrid=np.linspace(2.0, 7.0, 26), xg=np.linspace(-2, 8, 41),
                      yg=np.linspace(0, 12, 49), zg=np.linspace(0.5, 12, 24)):
    best = (np.inf, None)
    S = np.array([stations[sid[i]] for i in idx])
    tt = t[idx]
    for v in vgrid:
        for x in xg:
            for y in yg:
                for z in zg:
                    d = np.sqrt(((S - np.array([x, y, z]))**2).sum(axis=1))
                    tau = d / v
                    t0 = float(np.mean(tt - tau))
                    rms = float(np.sqrt(np.mean((tt - tau - t0)**2)))
                    if rms < best[0]:
                        best = (rms, dict(x=float(x), y=float(y), z=float(z), v=float(v), t0=t0))
    return best

rms_all, sol_all = fit_single_source(np.arange(len(t)))
print(f"[A] single common source for all 12 picks (repeated stations): best RMS={rms_all:.4f} s at {sol_all}")
# first pick per station only (5 picks, 5 distinct stations)
first_idx = np.array([int(np.where(np.array(sid) == s)[0][0]) for s in sta_ids])
rms_f, sol_f = fit_single_source(first_idx)
print(f"[B] single source from first pick at each station (5 picks, 1 dof after v grid): best RMS={rms_f:.4f} s at {sol_f}")
summary["single_source_all12_rms_s"] = rms_all
summary["single_source_all12_best"] = sol_all
summary["single_source_first5_rms_s"] = rms_f
summary["single_source_first5_best"] = sol_f

# Expected spread of uncertainties: pick scatter vs physical moveout
# Max physical time difference across the array at v=3..6 km/s
for v in (3.0, 6.0):
    print(f"max moveout across array at {v} km/s: {summary['max_pair_distance_km']/v:.3f} s")
print(f"pick scatter (resid_lin RMS) = {summary['linear_resid_rms_s']:.4f} s")
summary["max_moveout_s_v3"] = summary["max_pair_distance_km"]/3.0
summary["max_moveout_s_v6"] = summary["max_pair_distance_km"]/6.0

with open(os.path.join(OUTD, "summary.json"), "w") as f:
    json.dump(summary, f, indent=2, default=float)
print("\nwrote outputs/summary.json")
