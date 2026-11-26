"""Air pollution and respiratory clinic visits: daily panel analysis.

Stdlib + numpy only. Input is read-only: data/daily_panel.csv.
Run as: python3 -I code/analysis.py  (from the workspace root)
"""
import csv
import json
import math
import os

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data", "daily_panel.csv")
OUT = os.path.join(ROOT, "outputs")
os.makedirs(OUT, exist_ok=True)

COLS = ["pm25", "respiratory_visits", "heating_degree_day", "flu_index", "school_holiday"]
rng = np.random.default_rng(20261126)


def load():
    with open(DATA, newline="") as f:
        rows = list(csv.DictReader(f))
    d = {"day_index": np.array([int(r["day_index"]) for r in rows])}
    for c in COLS:
        d[c] = np.array([float(r[c]) for r in rows])
    return d


def ols_nw(y, X, names, lags=3):
    """OLS with Newey-West (Bartlett kernel) HAC standard errors."""
    n, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ X.T @ y
    e = y - X @ b
    S = (X * e[:, None]).T @ (X * e[:, None])
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = (X[L:] * e[L:, None]).T @ (X[:-L] * e[:-L, None])
        S += w * (G + G.T)
    V = XtX_inv @ S @ XtX_inv * n / (n - k)
    se = np.sqrt(np.diag(V))
    t = b / se
    ss_res = float(e @ e)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot
    return {n_: {"coef": float(b[i]), "se_nw": float(se[i]), "t": float(t[i]),
                 "ci95": [float(b[i] - 1.96 * se[i]), float(b[i] + 1.96 * se[i])]}
            for i, n_ in enumerate(names)} | {"_n": n, "_r2": r2}


def design(d, cols, lag=0, rows=None):
    """Build regression matrix with pm25 lagged by `lag` days (dropping first `lag` rows)."""
    n = len(d["day_index"])
    idx = np.arange(lag, n)
    y = d["respiratory_visits"][idx]
    feats = []
    names = ["const"]
    feats.append(np.ones(len(idx)))
    for c in cols:
        if c == "pm25":
            feats.append(d["pm25"][idx - lag])
            names.append(f"pm25_lag{lag}")
        else:
            feats.append(d[c][idx])
            names.append(c)
    return y, np.column_stack(feats), names


def block_bootstrap(d, cols, lag, B=2000, block=7):
    """Moving-block bootstrap of the pm25 coefficient (OLS, no HAC needed)."""
    y, X, names = design(d, cols, lag)
    j = names.index(f"pm25_lag{lag}")
    n = len(y)
    coefs = []
    nb = int(math.ceil(n / block))
    for _ in range(B):
        starts = rng.integers(0, n - block + 1, size=nb)
        ids = np.concatenate([np.arange(s, s + block) for s in starts])[:n]
        b = np.linalg.lstsq(X[ids], y[ids], rcond=None)[0]
        coefs.append(b[j])
    coefs = np.array(coefs)
    return [float(np.percentile(coefs, 2.5)), float(np.percentile(coefs, 97.5))]


def main():
    d = load()
    n = len(d["day_index"])
    res = {"n_days": n}
    print(f"N days = {n}; day_index range {d['day_index'].min()}..{d['day_index'].max()}")
    assert np.all(np.diff(d["day_index"]) == 1), "day_index not consecutive"

    # 1. Descriptives and data quality
    desc = {}
    print("\n== Descriptives ==")
    for c in COLS:
        x = d[c]
        desc[c] = {"mean": float(x.mean()), "sd": float(x.std(ddof=1)), "min": float(x.min()),
                   "p25": float(np.percentile(x, 25)), "median": float(np.median(x)),
                   "p75": float(np.percentile(x, 75)), "max": float(x.max()),
                   "n_zero": int((x == 0).sum())}
        print(f"{c:22s} mean={x.mean():8.3f} sd={x.std(ddof=1):7.3f} min={x.min():6.2f} "
              f"med={np.median(x):7.2f} max={x.max():7.2f} zeros={int((x==0).sum())}")
    res["descriptives"] = desc
    print(f"holiday days (index): {d['day_index'][d['school_holiday']==1].tolist()}")
    print(f"pm25 zeros at index: {d['day_index'][d['pm25']==0].tolist()}")
    print(f"flu_index zeros at index: {d['day_index'][d['flu_index']==0].tolist()}")

    # 2. Correlations
    print("\n== Pearson / Spearman correlations ==")
    from itertools import combinations
    corr = {}
    def ranks(x):
        order = np.argsort(x, kind="mergesort")
        r = np.empty(len(x))
        r[order] = np.arange(len(x))
        # average ties
        for v in np.unique(x):
            m = x == v
            r[m] = r[m].mean()
        return r
    for a, b in combinations(COLS, 2):
        pr = float(np.corrcoef(d[a], d[b])[0, 1])
        sr = float(np.corrcoef(ranks(d[a]), ranks(d[b]))[0, 1])
        corr[f"{a}~{b}"] = {"pearson": pr, "spearman": sr}
        print(f"{a:22s} ~ {b:22s} r={pr:+.3f}  rho={sr:+.3f}")
    res["correlations"] = corr

    # 3. Main OLS with Newey-West SEs, lag 0 pm25 and covariates
    cov = ["heating_degree_day", "flu_index", "school_holiday"]
    models = {}
    print("\n== OLS (Newey-West SE, 3 lags) ==")
    for lag in [0, 1, 2, 3]:
        y, X, names = design(d, ["pm25"] + cov, lag)
        m = ols_nw(y, X, names)
        models[f"lag{lag}_full"] = m
        c = m[f"pm25_lag{lag}"]
        print(f"lag{lag} full: pm25 b={c['coef']:+.4f} SE={c['se_nw']:.4f} t={c['t']:+.2f} "
              f"CI=[{c['ci95'][0]:+.4f},{c['ci95'][1]:+.4f}] R2={m['_r2']:.3f} n={m['_n']}")
        for k in cov:
            cc = m[k]
            print(f"    {k:20s} b={cc['coef']:+.4f} SE={cc['se_nw']:.4f} t={cc['t']:+.2f}")
    # pm25 only (no covariates) at lag 0 and 1
    for lag in [0, 1]:
        y, X, names = design(d, ["pm25"], lag)
        m = ols_nw(y, X, names)
        models[f"lag{lag}_pm25_only"] = m
        c = m[f"pm25_lag{lag}"]
        print(f"lag{lag} pm25-only: b={c['coef']:+.4f} SE={c['se_nw']:.4f} t={c['t']:+.2f} R2={m['_r2']:.3f}")
    res["models"] = models

    # 4. Block bootstrap CI for the main lag-0 and lag-1 pm25 coefficient
    print("\n== Moving-block bootstrap (block=7d, B=2000) ==")
    boot = {}
    for lag in [0, 1]:
        ci = block_bootstrap(d, ["pm25"] + cov, lag)
        boot[f"lag{lag}"] = ci
        print(f"lag{lag} full pm25 coef bootstrap 95% CI = [{ci[0]:+.4f}, {ci[1]:+.4f}]")
    res["bootstrap_ci"] = boot

    # 5. Sensitivity: drop days with pm25 == 0 (possible censoring / missing coded as 0)
    keep = d["pm25"] > 0
    sub = {k: v[keep] for k, v in d.items()}
    sub_idx_consec = np.diff(sub["day_index"]) == 1
    print(f"\n== Sensitivity: drop pm25==0 (n={keep.sum()}) ==")
    # refit without lag structure (lag 0 only; dates non-consecutive so no lag)
    y = sub["respiratory_visits"]
    X = np.column_stack([np.ones(len(y)), sub["pm25"], sub["heating_degree_day"],
                         sub["flu_index"], sub["school_holiday"]])
    names = ["const", "pm25", "heating_degree_day", "flu_index", "school_holiday"]
    # Plain OLS SE (non-consecutive rows: HAC not meaningful)
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    s2 = e @ e / (len(y) - X.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    sens = {nm: {"coef": float(b[i]), "se_ols": float(se[i])} for i, nm in enumerate(names)}
    for nm in names:
        print(f"  {nm:20s} b={sens[nm]['coef']:+.4f} SE_ols={sens[nm]['se_ols']:.4f}")
    res["sensitivity_drop_pm25_zero"] = {"n": int(keep.sum()), "coefs": sens}

    # 6. Holiday comparison (raw means)
    h = d["school_holiday"] == 1
    hol = {"holiday_mean_visits": float(d["respiratory_visits"][h].mean()),
           "nonholiday_mean_visits": float(d["respiratory_visits"][~h].mean()),
           "n_holiday": int(h.sum())}
    print(f"\nHoliday mean visits {hol['holiday_mean_visits']:.2f} (n={hol['n_holiday']}) vs "
          f"non-holiday {hol['nonholiday_mean_visits']:.2f}")
    res["holiday_raw"] = hol

    # 7. PM2.5 level bands (lag-0 raw comparison)
    bands = [(0, 0.0001), (0.0001, 5), (5, 10), (10, 15), (15, 20), (20, 100)]
    band_tab = []
    print("\n== Visits by PM2.5 band (same day) ==")
    for lo, hi in bands:
        m = (d["pm25"] >= lo) & (d["pm25"] < hi) if lo > 0 else (d["pm25"] == 0)
        if lo == 0.0001:
            m = (d["pm25"] > 0) & (d["pm25"] < hi)
        if m.sum() == 0:
            continue
        row = {"band": f"[{lo},{hi})", "n": int(m.sum()),
               "mean_visits": float(d["respiratory_visits"][m].mean())}
        band_tab.append(row)
        print(f"  pm25 in {row['band']:12s} n={row['n']:3d} mean visits={row['mean_visits']:.1f}")
    res["pm25_bands"] = band_tab

    # Policy-scale effect: per +10 ug/m3, lag 0 and lag 1 full model
    eff = {}
    for lag in [0, 1]:
        c = models[f"lag{lag}_full"][f"pm25_lag{lag}"]
        eff[f"lag{lag}"] = {"per10_visits": 10 * c["coef"],
                            "per10_ci95": [10 * c["ci95"][0], 10 * c["ci95"][1]],
                            "pct_of_mean": 100 * 10 * c["coef"] / desc["respiratory_visits"]["mean"]}
        print(f"\nlag{lag}: +10 ug/m3 PM2.5 -> {eff[f'lag{lag}']['per10_visits']:+.2f} visits/day "
              f"({eff[f'lag{lag}']['pct_of_mean']:+.2f}% of mean), NW95% CI "
              f"[{eff[f'lag{lag}']['per10_ci95'][0]:+.2f},{eff[f'lag{lag}']['per10_ci95'][1]:+.2f}]")
    res["per10ug_effect"] = eff

    with open(os.path.join(OUT, "results.json"), "w") as f:
        json.dump(res, f, indent=2, default=float)
    print(f"\nWrote {os.path.join(OUT, 'results.json')}")


if __name__ == "__main__":
    main()
