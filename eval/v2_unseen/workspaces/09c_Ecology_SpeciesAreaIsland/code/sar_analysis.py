"""Species-area relationship (SAR) analysis for island_species.csv.

Models fitted:
  M1 power law:      S = c * A^z           (OLS on log10 S ~ log10 A)
  M2 linear:         S = a + b * A
  M3 logarithmic:    S = a + b * ln(A)     (Gleason-type)
Outputs: printed tables (captured to out/sar_analysis_log.txt), a figure in outputs/.
"""
import csv
import os
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data", "island_species.csv")
OUT = os.path.join(ROOT, "outputs")
os.makedirs(OUT, exist_ok=True)

rows = []
with open(DATA) as f:
    for r in csv.DictReader(f):
        rows.append((int(r["island_id"]), float(r["area_km2"]), float(r["species_richness"])))
ids = np.array([r[0] for r in rows])
A = np.array([r[1] for r in rows])
S = np.array([r[2] for r in rows])
n = len(A)
print(f"n = {n} islands; area range [{A.min():.3f}, {A.max():.3f}] km2; "
      f"richness range [{S.min():.0f}, {S.max():.0f}]")
print(f"Area: median {np.median(A):.3f}, mean {A.mean():.3f}; "
      f"Richness: median {np.median(S):.1f}, mean {S.mean():.2f}")
print(f"Pearson r(A,S) = {stats.pearsonr(A, S)[0]:.3f}; "
      f"Spearman rho = {stats.spearmanr(A, S)[0]:.3f} (p={stats.spearmanr(A, S)[1]:.2g})")
print()


def ols(x, y):
    """Return dict with coefficients, SEs, CIs, R2, AIC, residuals, hat diagonal."""
    X = np.column_stack([np.ones_like(x), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    k = X.shape[1]
    dof = len(y) - k
    sigma2 = resid @ resid / dof
    XtX_inv = np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(sigma2 * XtX_inv))
    tcrit = stats.t.ppf(0.975, dof)
    ss_tot = ((y - y.mean()) ** 2).sum()
    r2 = 1 - (resid @ resid) / ss_tot
    adj_r2 = 1 - (1 - r2) * (len(y) - 1) / dof
    m = len(y)
    aic = m * np.log(resid @ resid / m) + 2 * (k + 1)  # Gaussian AIC incl. sigma
    H = X @ XtX_inv @ X.T
    hat = np.diag(H)
    return dict(beta=beta, se=se, ci=np.column_stack([beta - tcrit * se, beta + tcrit * se]),
                resid=resid, r2=r2, adj_r2=adj_r2, aic=aic, sigma=np.sqrt(sigma2),
                hat=hat, dof=dof, X=X, XtX_inv=XtX_inv)


def predict(fit, xnew, kind):
    if kind == "power":
        return 10 ** (fit["beta"][0] + fit["beta"][1] * np.log10(xnew))
    if kind == "linear":
        return fit["beta"][0] + fit["beta"][1] * xnew
    if kind == "log":
        return fit["beta"][0] + fit["beta"][1] * np.log(xnew)


def fit_all(mask):
    a, s = A[mask], S[mask]
    res = {}
    # Power law in log10 space
    lp = ols(np.log10(a), np.log10(s))
    res["power"] = lp
    # Linear and log-linear on the natural scale
    res["linear"] = ols(a, s)
    res["log"] = ols(np.log(a), s)
    return res


def report_models(mask, label):
    print(f"=== {label} (n={mask.sum()}) ===")
    res = fit_all(mask)
    lp = res["power"]
    c = 10 ** lp["beta"][0]
    z, z_se = lp["beta"][1], lp["se"][1]
    zlo, zhi = lp["ci"][1]
    print(f"Power law  log10 S = log10 c + z log10 A:")
    print(f"  c = {c:.3f}  (log10 c = {lp['beta'][0]:.4f}),  z = {z:.4f} "
          f"(SE {z_se:.4f}, 95% CI [{zlo:.4f}, {zhi:.4f}])")
    print(f"  R2(log) = {lp['r2']:.4f}, adjR2 = {lp['adj_r2']:.4f}, AIC(log space) = {lp['aic']:.2f}, "
          f"residual SD (log10) = {lp['sigma']:.4f}")
    # Back-transformed fit statistics on natural scale for fair comparison
    a, s = A[mask], S[mask]
    for kind in ["power", "linear", "log"]:
        pred = predict(res[kind], a, kind)
        rss = ((s - pred) ** 2).sum()
        r2_nat = 1 - rss / ((s - s.mean()) ** 2).sum()
        m = len(s)
        k = 3  # two coefficients + sigma
        aic_nat = m * np.log(rss / m) + 2 * k
        if kind == "power":
            aic_power_nat = aic_nat
        print(f"  [{kind:6s}] natural-scale R2 = {r2_nat:.4f}, RMSE = {np.sqrt(rss/m):.3f}, "
              f"AIC(natural scale) = {aic_nat:.2f}")
    lin = res["linear"]; lg = res["log"]
    print(f"Linear   S = a + b A:  a = {lin['beta'][0]:.3f}, b = {lin['beta'][1]:.3f} "
          f"(95% CI [{lin['ci'][1][0]:.3f}, {lin['ci'][1][1]:.3f}])")
    print(f"Log      S = a + b lnA:  a = {lg['beta'][0]:.3f}, b = {lg['beta'][1]:.3f} "
          f"(95% CI [{lg['ci'][1][0]:.3f}, {lg['ci'][1][1]:.3f}])")
    print()
    return res


full = np.ones(n, dtype=bool)
res_full = report_models(full, "All islands")

# Influence diagnostics on the power-law fit (log space)
lp = res_full["power"]
h = lp["hat"]
p = lp["X"].shape[1]
s2 = lp["sigma"] ** 2
resid = lp["resid"]
# Studentized residuals
stud = resid / (lp["sigma"] * np.sqrt(1 - h))
# Cook's distance
cook = (stud ** 2) * h / (p * (1 - h))
print("Influence diagnostics (power-law fit, log space):")
print(f"{'id':>3} {'area':>7} {'S':>5} {'resid(log10)':>13} {'stud_res':>9} {'hat':>6} {'Cook_D':>7}")
for i in np.argsort(-cook)[:6]:
    print(f"{ids[i]:>3} {A[i]:>7.3f} {S[i]:>5.0f} {resid[i]:>13.4f} {stud[i]:>9.3f} {h[i]:>6.3f} {cook[i]:>7.3f}")
print(f"Cook's D rule of thumb 4/n = {4/n:.3f}; "
      f"islands exceeding: {[int(ids[i]) for i in range(n) if cook[i] > 4/n]}")
print()

# Sensitivity: drop the two high-residual islands (3 and 17) identified above
flagged = np.isin(ids, [3, 17])
res_sens = report_models(~flagged, "Sensitivity: excluding islands 3 and 17")

# Leave-one-out cross-validation for prediction error (natural scale)
print("Leave-one-out cross-validation (natural-scale RMSE, lower is better):")
loo = {"null_mean": [], "power": [], "linear": [], "log": []}
for i in range(n):
    m = np.ones(n, dtype=bool); m[i] = False
    r = fit_all(m)
    loo["null_mean"].append(S[i] - S[m].mean())
    for kind in ["power", "linear", "log"]:
        loo[kind].append(S[i] - predict(r[kind], A[i:i+1], kind)[0])
for kind in loo:
    e = np.array(loo[kind])
    print(f"  {kind:6s}: LOO RMSE = {np.sqrt(np.mean(e**2)):.3f}, MAE = {np.mean(np.abs(e)):.3f}")
print()

# Power-law fit excluding the two flagged islands: 95% prediction intervals
print("Prediction table (power law, all islands; 95% prediction interval on log10 S):")
lp = res_full["power"]
dof = lp["dof"]
tcrit = stats.t.ppf(0.975, dof)
for a_new in [0.5, 1, 2, 5, 10, 25, 50, 100, 500]:
    x0 = np.array([1.0, np.log10(a_new)])
    yhat = x0 @ lp["beta"]
    var_pred = lp["sigma"] ** 2 * (1 + x0 @ lp["XtX_inv"] @ x0)
    half = tcrit * np.sqrt(var_pred)
    print(f"  A = {a_new:>6} km2: S_hat = {10**yhat:7.2f} "
          f"(PI95 log-scale [{10**(yhat-half):.1f}, {10**(yhat+half):.1f}])"
          + ("  <- extrapolation beyond data" if a_new > A.max() else ""))
print()
print("Same predictions from the sensitivity fit (islands 3 and 17 excluded):")
lp_s = res_sens["power"]
tcrit_s = stats.t.ppf(0.975, lp_s["dof"])
for a_new in [1, 2, 5, 10, 25, 50]:
    x0 = np.array([1.0, np.log10(a_new)])
    yhat = x0 @ lp_s["beta"]
    half = tcrit_s * np.sqrt(lp_s["sigma"] ** 2 * (1 + x0 @ lp_s["XtX_inv"] @ x0))
    print(f"  A = {a_new:>3} km2: S_hat = {10**yhat:6.2f} (PI95 [{10**(yhat-half):.1f}, {10**(yhat+half):.1f}])")
print()

# Conservation implications: species loss from habitat reduction under power law
print("Expected proportional species loss when habitat is reduced (power law, z from full fit):")
z_full = lp["beta"][1]
z_lo, z_hi = lp["ci"][1]
print(f"  (sensitivity-fit z = {res_sens['power']['beta'][1]:.4f}; losses change by <0.5 pct-pt at 10-50% reduction)")
for frac in [0.10, 0.25, 0.50, 0.75, 0.90]:
    loss = 1 - (1 - frac) ** z_full
    loss_lo = 1 - (1 - frac) ** z_lo
    loss_hi = 1 - (1 - frac) ** z_hi
    print(f"  area reduced by {int(frac*100):>2}%: loss = {loss*100:5.1f}% "
          f"(z CI gives [{min(loss_lo,loss_hi)*100:.1f}%, {max(loss_lo,loss_hi)*100:.1f}%])")
print()
print("Habitat area that must be retained (power law, full-fit z) to keep a target fraction of species:")
for keep in [0.90, 0.80, 0.50]:
    frac_area = keep ** (1 / z_full)
    print(f"  retain {int(keep*100)}% of species: keep {int(frac_area*100)}% of habitat (i.e. may lose {int((1-frac_area)*100)}%)")
print()

# Figure
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
ax = axes[0]
ax.scatter(A, S, c=np.where(flagged, "tab:red", "tab:blue"), zorder=3)
for i in range(n):
    ax.annotate(str(ids[i]), (A[i], S[i]), fontsize=7, xytext=(3, 3), textcoords="offset points")
xs = np.logspace(np.log10(A.min() * 0.8), np.log10(A.max() * 1.2), 200)
ax.plot(xs, predict(res_full["power"], xs, "power"), label=f"power law (z={z_full:.3f})")
ax.plot(xs, predict(res_full["linear"], xs, "linear"), ls="--", label="linear")
ax.plot(xs, predict(res_full["log"], xs, "log"), ls=":", label="logarithmic")
ax.set_xscale("log"); ax.set_xlabel("Area (km², log scale)"); ax.set_ylabel("Species richness")
ax.set_title("Species-area relationship (red = high-residual islands)")
ax.legend(fontsize=8)
ax = axes[1]
ax.scatter(np.log10(A), np.log10(S), color="tab:blue")
xl = np.linspace(np.log10(A.min()), np.log10(A.max()), 50)
ax.plot(xl, lp["beta"][0] + lp["beta"][1] * xl, color="k")
ax.set_xlabel("log10 area"); ax.set_ylabel("log10 richness"); ax.set_title("Log-log fit")
plt.tight_layout()
fig_path = os.path.join(OUT, "sar_fit.png")
plt.savefig(fig_path, dpi=150)
print(f"Saved figure: {fig_path}")
