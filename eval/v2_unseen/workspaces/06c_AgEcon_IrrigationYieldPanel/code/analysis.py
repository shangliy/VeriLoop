"""Irrigation-yield association analysis for data/field_year_panel.csv.

Run: python3 -I code/analysis.py  (from workspace root)
Outputs printed to stdout (captured to out/analysis_log.txt).
"""
import csv
import numpy as np
from scipy import stats

PATH = "data/field_year_panel.csv"
rng = np.random.default_rng(20261126)

rows = list(csv.DictReader(open(PATH)))
cols = ["plot_id", "yield_t_ha", "irrigation_m3", "fertilizer_kg",
        "groundwater_quota_enforcement", "rainfall_mm"]
D = {c: np.array([float(r[c]) for r in rows]) for c in cols}
n = len(rows)
print(f"N rows = {n}; unique plot_id = {len(set(r['plot_id'] for r in rows))}")
print("Columns:", list(rows[0].keys()))
print("Year / time / treatment column present: NO")

print("\n== Descriptives ==")
for c in cols[1:]:
    x = D[c]
    print(f"{c:32s} mean={x.mean():9.3f} sd={x.std(ddof=1):8.3f} "
          f"min={x.min():8.3f} med={np.median(x):8.3f} max={x.max():8.3f}")

print("\n== Pearson correlations (r, p) ==")
preds = ["irrigation_m3", "fertilizer_kg", "groundwater_quota_enforcement", "rainfall_mm"]
for p in preds:
    r, pv = stats.pearsonr(D[p], D["yield_t_ha"])
    print(f"yield ~ {p:32s} r={r:+.3f} p={pv:.4f}")
print("Collinearity among regressors:")
for i, a in enumerate(preds):
    for b in preds[i + 1:]:
        r, pv = stats.pearsonr(D[a], D[b])
        print(f"  {a} vs {b}: r={r:+.3f} p={pv:.4f}")


def ols(y, X, names):
    """OLS with HC1 robust SEs. X includes intercept column."""
    k = X.shape[1]
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    e = y - X @ beta
    meat = X.T @ (X * (e ** 2)[:, None])
    V = (n / (n - k)) * XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.diag(V))
    t = beta / se
    p = 2 * stats.t.sf(np.abs(t), df=n - k)
    r2 = 1 - (e @ e) / np.sum((y - y.mean()) ** 2)
    adj = 1 - (1 - r2) * (n - 1) / (n - k)
    print(f"{'term':28s}{'coef':>12s}{'HC1 se':>11s}{'t':>8s}{'p':>9s}")
    for nm, b, s, tt, pp in zip(names, beta, se, t, p):
        print(f"{nm:28s}{b:12.5f}{s:11.5f}{tt:8.2f}{pp:9.4f}")
    print(f"R2={r2:.3f} adjR2={adj:.3f} n={n} k={k}")
    return beta, se


y = D["yield_t_ha"]
one = np.ones(n)
# Scale: irrigation per 100 m3, fertilizer per 10 kg, quota as 0-1 score, rain per 100 mm
irr100 = D["irrigation_m3"] / 100
fert10 = D["fertilizer_kg"] / 10
quota = D["groundwater_quota_enforcement"]
rain100 = D["rainfall_mm"] / 100

print("\n== Model 1: yield ~ irrigation (bivariate) ==")
ols(y, np.column_stack([one, irr100]), ["const", "irrigation per 100 m3"])

print("\n== Model 2: yield ~ irrigation + fertilizer + quota + rainfall ==")
b2, s2 = ols(y, np.column_stack([one, irr100, fert10, quota, rain100]),
             ["const", "irrigation per 100 m3", "fertilizer per 10 kg",
              "quota enforcement (0-1)", "rainfall per 100 mm"])

print("\n== Model 3: Model 2 + irrigation x quota interaction (quota centered) ==")
qc = quota - quota.mean()
ols(y, np.column_stack([one, irr100, fert10, quota, rain100, irr100 * qc]),
    ["const", "irrigation per 100 m3", "fertilizer per 10 kg",
     "quota enforcement (0-1)", "rainfall per 100 mm", "irrig x quota(centered)"])

print("\n== Model 4: Model 2 + irrigation^2 (curvature check) ==")
ols(y, np.column_stack([one, irr100, irr100 ** 2, fert10, quota, rain100]),
    ["const", "irrigation per 100 m3", "irrigation^2 (100m3)^2",
     "fertilizer per 10 kg", "quota enforcement (0-1)", "rainfall per 100 mm"])

print("\n== Bootstrap (2000 reps, resampling plots) for Model 2 irrigation coef ==")
X2 = np.column_stack([one, irr100, fert10, quota, rain100])
boot = []
for _ in range(2000):
    idx = rng.integers(0, n, n)
    Xb, yb = X2[idx], y[idx]
    try:
        boot.append(np.linalg.lstsq(Xb, yb, rcond=None)[0][1])
    except np.linalg.LinAlgError:
        pass
boot = np.array(boot)
lo, hi = np.percentile(boot, [2.5, 97.5])
print(f"irrigation coef point={b2[1]:.5f}  bootstrap 95% CI=[{lo:.5f}, {hi:.5f}]  "
      f"share of boot draws > 0: {np.mean(boot > 0):.3f}")

print("\n== Stratified descriptives: irrigation terciles ==")
q1, q2 = np.percentile(D["irrigation_m3"], [33.33, 66.67])
bins = {"low": D["irrigation_m3"] <= q1,
        "mid": (D["irrigation_m3"] > q1) & (D["irrigation_m3"] <= q2),
        "high": D["irrigation_m3"] > q2}
for k, m in bins.items():
    print(f"irrig {k:4s} n={m.sum():2d} mean yield={y[m].mean():.3f} "
          f"sd={y[m].std(ddof=1):.3f} mean quota={quota[m].mean():.3f} "
          f"mean rain={D['rainfall_mm'][m].mean():.1f}")
H, p_kw = stats.kruskal(y[bins["low"]], y[bins["mid"]], y[bins["high"]])
print(f"Kruskal-Wallis yield across irrigation terciles: H={H:.3f} p={p_kw:.4f}")

print("\n== Stratified descriptives: quota-enforcement terciles ==")
g1, g2 = np.percentile(quota, [33.33, 66.67])
qbins = {"low": quota <= g1,
         "mid": (quota > g1) & (quota <= g2),
         "high": quota > g2}
for k, m in qbins.items():
    print(f"quota {k:4s} n={m.sum():2d} mean yield={y[m].mean():.3f} "
          f"sd={y[m].std(ddof=1):.3f} mean irrig={D['irrigation_m3'][m].mean():.1f}")
H, p_kw = stats.kruskal(y[qbins["low"]], y[qbins["mid"]], y[qbins["high"]])
print(f"Kruskal-Wallis yield across quota terciles: H={H:.3f} p={p_kw:.4f}")

print("\n== Irrigation slope within quota strata (bivariate, per 100 m3) ==")
for k, m in qbins.items():
    b, *_ = np.linalg.lstsq(np.column_stack([np.ones(m.sum()), irr100[m]]), y[m], rcond=None)[0:1]
    r, pv = stats.pearsonr(irr100[m], y[m])
    print(f"quota {k:4s} n={m.sum():2d} slope={b[1] if np.ndim(b) else b:+.4f} r={r:+.3f} p={pv:.4f}")

print("\n== Water-use efficiency: yield per 100 m3 irrigation (descriptive, ill-defined at low irrigation) ==")
wue = y / np.maximum(irr100, 1e-9)
print(f"median yield/(100 m3) = {np.median(wue):.3f}; rows with irrigation < 20 m3: "
      f"{int(np.sum(D['irrigation_m3'] < 20))}")
