"""Annual-outlook and reliability analysis for load_15min.csv (numpy + matplotlib only).

Outputs:
  outputs/qa_summary.json, outputs/daily_summary.csv, outputs/hourly_profile.csv,
  outputs/backtest_metrics.csv, outputs/annual_scenarios.csv,
  outputs/fig_timeseries.png, outputs/fig_profile_backtest.png
"""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data", "load_15min.csv")
OUT = os.path.join(ROOT, "outputs")
os.makedirs(OUT, exist_ok=True)

# ---------------- 1. Load and QA ----------------
lines = open(DATA).read().splitlines()
header, rows = lines[0], lines[1:]
ts = np.array([r.split(",")[0] for r in rows])
raw = [r.split(",")[1] for r in rows]
v = np.array([float(x) if x.strip() != "" else np.nan for x in raw])
t = np.array([np.datetime64(s.replace("Z", "")) for s in ts])
N = len(v)
miss = np.isnan(v)
valid = v[~miss]

steps = np.unique(np.diff(t).astype("timedelta64[m]").astype(int))
dups = N - len(np.unique(t))
# contiguous missing runs
runs = []
idx = np.where(miss)[0]
if len(idx):
    s = p = idx[0]
    for i in idx[1:]:
        if i != p + 1:
            runs.append((s, p)); s = i
        p = i
    runs.append((s, p))
run_info = [{"start": str(t[a]), "end": str(t[b]), "n_intervals": int(b - a + 1),
             "hours": float((b - a + 1) * 0.25)} for a, b in runs]

qa = {
    "header": header,
    "n_rows": int(N),
    "first_timestamp": str(t[0]), "last_timestamp": str(t[-1]),
    "calendar_days": int(len(np.unique(t.astype("datetime64[D]")))),
    "sampling_minutes_unique": steps.tolist(),
    "duplicate_timestamps": int(dups),
    "missing_values": int(miss.sum()),
    "missing_fraction": float(miss.mean()),
    "missing_runs": run_info,
    "min_MW": float(valid.min()), "max_MW": float(valid.max()),
    "mean_MW": float(valid.mean()), "median_MW": float(np.median(valid)),
    "std_MW": float(valid.std()),
}

# ---------------- 2. Descriptive statistics ----------------
days = np.array([str(d) for d in t.astype("datetime64[D]")])
hours = np.array([int(str(x)[11:13]) for x in t])
slot = np.array([int(str(x)[11:13]) * 4 + int(str(x)[14:16]) // 15 for x in t])  # 0..95
uniq_days = sorted(set(days))

daily_rows = []
for d in uniq_days:
    m = days == d
    vv = v[m]; ok = ~np.isnan(vv)
    energy = float(np.sum(vv[ok]) * 0.25)  # MWh
    cover = float(ok.mean())
    # energy scaled to a full day for days with gaps (coverage-weighted), reported separately
    daily_rows.append([d, int(ok.sum()), cover, float(np.mean(vv[ok])) if ok.any() else np.nan,
                       float(np.max(vv[ok])) if ok.any() else np.nan,
                       float(np.min(vv[ok])) if ok.any() else np.nan, energy])
with open(os.path.join(OUT, "daily_summary.csv"), "w") as f:
    f.write("date,valid_intervals,coverage,mean_MW,max_MW,min_MW,energy_MWh_observed\n")
    for r in daily_rows:
        f.write(f"{r[0]},{r[1]},{r[2]:.4f},{r[3]:.3f},{r[4]:.3f},{r[5]:.3f},{r[6]:.2f}\n")

# hourly profile (mean of valid intervals in each hour across all days)
hourly = np.array([np.nanmean(v[hours == h]) for h in range(24)])
hourly_min = np.array([np.nanmin(v[hours == h]) for h in range(24)])
hourly_max = np.array([np.nanmax(v[hours == h]) for h in range(24)])
with open(os.path.join(OUT, "hourly_profile.csv"), "w") as f:
    f.write("hour,mean_MW,min_MW,max_MW\n")
    for h in range(24):
        f.write(f"{h},{hourly[h]:.3f},{hourly_min[h]:.3f},{hourly_max[h]:.3f}\n")

# percentiles and peak/average
pcts = {p: float(np.percentile(valid, p)) for p in [1, 5, 50, 95, 99, 99.9]}
qa["percentiles_MW"] = pcts
qa["peak_to_average"] = float(valid.max() / valid.mean())
qa["load_factor_week"] = float(valid.mean() / valid.max())
qa["peak_time"] = str(t[np.nanargmax(v)])
qa["trough_time"] = str(t[np.nanargmin(v)])

# weekday vs weekend (observed days only; 2026-01-03 Sat, 01-04 Sun are weekend)
wd = np.array([np.datetime64(d).astype("datetime64[D]").astype(int) for d in days])
dow = (wd + 3) % 7  # 1970-01-01 was Thursday; Monday=0
weekend = dow >= 5
qa["weekend_mean_MW"] = float(np.nanmean(v[weekend]))
qa["weekday_mean_MW"] = float(np.nanmean(v[~weekend]))
qa["weekday_names_of_days"] = {d: ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][int(dow[days == d][0])] for d in uniq_days}

# 15-min ramp rates (only consecutive valid pairs)
d15 = np.diff(v)
d15 = d15[~np.isnan(d15)]
qa["ramp_15min_MW"] = {"p50_abs": float(np.percentile(np.abs(d15), 50)),
                       "p99_abs": float(np.percentile(np.abs(d15), 99)),
                       "max_abs": float(np.max(np.abs(d15))),
                       "max_up": float(np.max(d15)), "max_down": float(np.min(d15))}

# ---------------- 3. Short-horizon backtest (day-ahead, prior data only) ----------------
def fc_persistence(target_day):
    prev = [d for d in uniq_days if d < target_day][-1]
    return v[days == prev]

def fc_slot_mean(target_day):
    prior = np.array([d < target_day for d in days])
    out = np.full(96, np.nan)
    for s_ in range(96):
        vals = v[prior & (slot == s_)]
        out[s_] = np.nanmean(vals) if np.any(~np.isnan(vals)) else np.nan
    return out

def fc_flat(target_day):
    prior = np.array([d < target_day for d in days])
    m = np.nanmean(v[prior])
    return np.full(96, m)

def metrics(y, f):
    ok = ~np.isnan(y) & ~np.isnan(f)
    e = y[ok] - f[ok]
    return {"n": int(ok.sum()), "MAE_MW": float(np.mean(np.abs(e))),
            "RMSE_MW": float(np.sqrt(np.mean(e ** 2))),
            "MAPE_pct": float(np.mean(np.abs(e) / y[ok]) * 100)}

bt_rows = []
bt_store = {}
for target in ["2026-01-05", "2026-01-06", "2026-01-07"]:
    y = v[days == target]
    for name, fn in [("persistence_prev_day", fc_persistence),
                     ("slot_mean_prior_days", fc_slot_mean),
                     ("flat_prior_mean", fc_flat)]:
        f = fn(target)
        m = metrics(y, f)
        bt_rows.append((target, name, m))
        bt_store[(target, name)] = f
with open(os.path.join(OUT, "backtest_metrics.csv"), "w") as f:
    f.write("target_day,method,n,MAE_MW,RMSE_MW,MAPE_pct\n")
    for tgt, name, m in bt_rows:
        f.write(f"{tgt},{name},{m['n']},{m['MAE_MW']:.3f},{m['RMSE_MW']:.3f},{m['MAPE_pct']:.3f}\n")
# pooled over the three backtest days
pooled = {}
for name in ["persistence_prev_day", "slot_mean_prior_days", "flat_prior_mean"]:
    ys, fs = [], []
    for target in ["2026-01-05", "2026-01-06", "2026-01-07"]:
        ys.append(v[days == target]); fs.append(bt_store[(target, name)])
    pooled[name] = metrics(np.concatenate(ys), np.concatenate(fs))

# ---------------- 4. Annual outlook (scenario arithmetic, NOT a fitted annual forecast) ----------------
mean_obs = float(valid.mean())
peak_obs = float(valid.max())
hours_per_year = 8760
annual_energy_flat = mean_obs * hours_per_year  # MWh
scen = []
for growth in [0.0, 0.01, 0.02, 0.03]:
    for peak_uplift in [0.00, 0.05, 0.10, 0.15]:
        e_ann = annual_energy_flat * (1 + growth)
        p_ann = peak_obs * (1 + growth) * (1 + peak_uplift)
        scen.append((growth, peak_uplift, e_ann, p_ann))
with open(os.path.join(OUT, "annual_scenarios.csv"), "w") as f:
    f.write("growth_pct_per_yr,peak_uplift_pct,annual_energy_GWh,annual_peak_MW_planning\n")
    for g, u, e, p in scen:
        f.write(f"{g*100:.1f},{u*100:.1f},{e/1000:.1f},{p:.2f}\n")

qa["annual_energy_flat_GWh_at_week_mean"] = annual_energy_flat / 1000
qa["annual_energy_flat_range_note"] = "week-mean x 8760 h; ignores seasonality"
qa["planning_peak_base_MW"] = peak_obs

with open(os.path.join(OUT, "qa_summary.json"), "w") as f:
    json.dump({"qa": qa, "backtest_pooled": pooled,
               "backtest_by_day": {f"{a}|{b}": c for a, b, c in bt_rows}}, f, indent=2, default=float)

# ---------------- 5. Figures ----------------
fig, ax = plt.subplots(figsize=(12, 4))
ax.plot(t, v, lw=0.7, color="#1f4e79", label="load (MW)")
ax.axvspan(t[miss][0], t[miss][-1] + np.timedelta64(15, "m"), color="orange", alpha=0.25,
           label="missing (2026-01-01 20:00 to 01-03 01:45)")
ax.set_ylabel("MW"); ax.set_title("15-minute load, 2026-01-01 to 2026-01-07")
ax.legend(loc="lower left"); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_timeseries.png"), dpi=130); plt.close(fig)

fig, axs = plt.subplots(1, 2, figsize=(12, 4))
axs[0].fill_between(range(24), hourly_min, hourly_max, color="#9dc3e6", alpha=0.5, label="min-max")
axs[0].plot(range(24), hourly, color="#1f4e79", marker="o", ms=3, label="mean")
axs[0].set_xlabel("hour of day (UTC)"); axs[0].set_ylabel("MW"); axs[0].set_title("Hourly profile")
axs[0].legend(); axs[0].grid(alpha=0.3)
x = np.arange(96) / 4
y5 = v[days == "2026-01-07"]
axs[1].plot(x, y5, color="black", lw=1.2, label="actual 2026-01-07")
axs[1].plot(x, bt_store[("2026-01-07", "slot_mean_prior_days")], lw=1, label="slot-mean forecast")
axs[1].plot(x, bt_store[("2026-01-07", "persistence_prev_day")], lw=1, ls="--", label="persistence")
axs[1].set_xlabel("hour of day (UTC)"); axs[1].set_ylabel("MW"); axs[1].set_title("Day-ahead backtest, 2026-01-07")
axs[1].legend(); axs[1].grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_profile_backtest.png"), dpi=130); plt.close(fig)

# ---------------- 6. Print report-ready numbers ----------------
print("=== QA ===")
for k in ["n_rows", "first_timestamp", "last_timestamp", "calendar_days", "sampling_minutes_unique",
          "duplicate_timestamps", "missing_values", "missing_fraction", "min_MW", "max_MW", "mean_MW",
          "median_MW", "std_MW", "peak_to_average", "load_factor_week", "peak_time", "trough_time",
          "weekend_mean_MW", "weekday_mean_MW", "ramp_15min_MW", "percentiles_MW"]:
    print(f"{k}: {qa[k]}")
print("missing_runs:", json.dumps(run_info))
print("weekday_names_of_days:", qa["weekday_names_of_days"])
print("\n=== Daily (observed) ===")
for r in daily_rows:
    print(f"{r[0]} valid={r[1]:3d} cov={r[2]:.2f} mean={r[3]:.2f} max={r[4]:.2f} min={r[5]:.2f} energy_obs={r[6]:.1f} MWh")
print("\n=== Hourly mean (UTC) ===")
for h in range(24):
    print(f"h{h:02d} mean={hourly[h]:.2f} min={hourly_min[h]:.2f} max={hourly_max[h]:.2f}")
print("\n=== Backtest per day ===")
for tgt, name, m in bt_rows:
    print(f"{tgt} {name:22s} n={m['n']:3d} MAE={m['MAE_MW']:.3f} RMSE={m['RMSE_MW']:.3f} MAPE={m['MAPE_pct']:.2f}%")
print("=== Backtest pooled ===")
for name, m in pooled.items():
    print(f"{name:22s} n={m['n']} MAE={m['MAE_MW']:.3f} RMSE={m['RMSE_MW']:.3f} MAPE={m['MAPE_pct']:.2f}%")
print("\n=== Annual scenarios (growth, peak uplift -> energy GWh, planning peak MW) ===")
for g, u, e, p in scen:
    print(f"growth={g*100:.0f}% uplift={u*100:.0f}% energy={e/1000:.1f} GWh peak={p:.1f} MW")
print("\nFlat annual energy (week mean x 8760):", round(annual_energy_flat / 1000, 1), "GWh")
