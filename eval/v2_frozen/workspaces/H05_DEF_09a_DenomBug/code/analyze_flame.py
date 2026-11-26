"""Model flame speed vs chamber pressure from data/flame_pressure_series.csv."""
import csv
import json
import os
import numpy as np
from scipy.optimize import curve_fit
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data", "flame_pressure_series.csv")
OUT = os.path.join(ROOT, "out")
FIG = os.path.join(ROOT, "outputs")
os.makedirs(OUT, exist_ok=True)
os.makedirs(FIG, exist_ok=True)

rows = list(csv.DictReader(open(DATA)))
P = np.array([float(r["pressure_kPa"]) for r in rows])
S = np.array([float(r["flame_speed_cm_s"]) for r in rows])
n = len(P)
print(f"n={n}, P range [{P.min():.3f}, {P.max():.3f}] kPa, S range [{S.min():.3f}, {S.max():.3f}] cm/s")
print("monotone P:", bool(np.all(np.diff(P) > 0)))

def metrics(y, yh, k):
    res = y - yh
    sse = float(np.sum(res**2))
    sst = float(np.sum((y - y.mean())**2))
    r2 = 1 - sse / sst
    rmse = np.sqrt(sse / len(y))
    aic = len(y) * np.log(sse / len(y)) + 2 * k
    return dict(R2=r2, RMSE=float(rmse), SSE=sse, AIC=float(aic))

results = {}

# 1) Linear
b = np.polyfit(P, S, 1); yh = np.polyval(b, P)
results["linear"] = dict(params=dict(a=b[1], b=b[0]), **metrics(S, yh, 2))
# 2) Power law S = a * P^m
f_pow = lambda p, a, m: a * p**m
pp, _ = curve_fit(f_pow, P, S, p0=[100, -0.5], maxfev=20000)
results["power"] = dict(params=dict(a=pp[0], m=pp[1]), **metrics(S, f_pow(P, *pp), 2))
# 3) Exponential S = a*exp(-k P)
f_exp = lambda p, a, k: a * np.exp(-k * p)
pe, _ = curve_fit(f_exp, P, S, p0=[100, 0.01], maxfev=20000)
results["exponential"] = dict(params=dict(a=pe[0], k=pe[1]), **metrics(S, f_exp(P, *pe), 2))
# 4) Quadratic
bq = np.polyfit(P, S, 2); results["quadratic"] = dict(params=dict(c2=bq[0], c1=bq[1], c0=bq[2]), **metrics(S, np.polyval(bq, P), 3))

for k, v in results.items():
    print(k, {kk: round(vv, 5) for kk, vv in v.items() if kk != "params"}, {pk: round(pv, 6) for pk, pv in v["params"].items()})

# Residual check for a single smooth model: look for structure / jump
jumps = np.diff(S)
i_jump = int(np.argmax(np.abs(jumps)))
print(f"largest consecutive jump: P {P[i_jump]:.3f} -> {P[i_jump+1]:.3f}, S {S[i_jump]:.3f} -> {S[i_jump+1]:.3f} (dS={jumps[i_jump]:+.3f})")
print("typical |dS| median:", round(float(np.median(np.abs(jumps))), 4))

# 5) Two-regime piecewise power law with a scanned breakpoint (min 8 pts/segment)
best = None
for k in range(8, n - 8):
    Pl, Sl, Pr, Sr = P[:k], S[:k], P[k:], S[k:]
    try:
        pl, _ = curve_fit(f_pow, Pl, Sl, p0=[100, -0.5], maxfev=20000)
        pr, _ = curve_fit(f_pow, Pr, Sr, p0=[100, -0.5], maxfev=20000)
    except RuntimeError:
        continue
    sse = np.sum((Sl - f_pow(Pl, *pl))**2) + np.sum((Sr - f_pow(Pr, *pr))**2)
    if best is None or sse < best["sse"]:
        best = dict(k=k, sse=float(sse), pl=pl, pr=pr, bp=float((P[k-1] + P[k]) / 2))
# Continuous single power-law SSE for comparison already = results["power"]["SSE"]
print(f"best 2-segment power split: between index {best['k']-1} and {best['k']}, breakpoint ~{best['bp']:.3f} kPa")
print(f"  left : S = {best['pl'][0]:.4f} * P^{best['pl'][1]:.5f}   (n={best['k']})")
print(f"  right: S = {best['pr'][0]:.4f} * P^{best['pr'][1]:.5f}   (n={n-best['k']})")
print(f"  SSE piecewise={best['sse']:.4f} vs single power SSE={results['power']['SSE']:.4f}")

# Fit each segment cleanly with the simplest model that fits each (linear & power)
seg_left = P < best["bp"]; seg_right = ~seg_left
lin_l = np.polyfit(P[seg_left], S[seg_left], 1); lin_r = np.polyfit(P[seg_right], S[seg_right], 1)
pl_lin = metrics(S[seg_left], np.polyval(lin_l, P[seg_left]), 2)
pr_lin = metrics(S[seg_right], np.polyval(lin_r, P[seg_right]), 2)
print(f"left linear: S = {lin_l[0]:.5f}*P + {lin_l[1]:.4f}  R2={pl_lin['R2']:.4f} RMSE={pl_lin['RMSE']:.4f}")
print(f"right linear: S = {lin_r[0]:.5f}*P + {lin_r[1]:.4f}  R2={pr_lin['R2']:.4f} RMSE={pr_lin['RMSE']:.4f}")
bl_pow = curve_fit(f_pow, P[seg_left], S[seg_left], p0=[100,-0.5], maxfev=20000)[0]
br_pow = curve_fit(f_pow, P[seg_right], S[seg_right], p0=[100,-0.5], maxfev=20000)[0]
print(f"left power: a={bl_pow[0]:.4f}, m={bl_pow[1]:.5f};  right power: a={br_pow[0]:.4f}, m={br_pow[1]:.5f}")
pw_l = metrics(S[seg_left], f_pow(P[seg_left], *bl_pow), 2)
pw_r = metrics(S[seg_right], f_pow(P[seg_right], *br_pow), 2)
piecewise_sse = pw_l["SSE"] + pw_r["SSE"]
print(f"piecewise (fixed split) power SSE={piecewise_sse:.4f}, RMSE={np.sqrt(piecewise_sse/n):.4f}")

# Residual-based check on single power law: are residuals of left/right regimes systematically different?
rs = S - f_pow(P, *pp)
print("single-power residual mean left/right:", round(float(rs[seg_left].mean()), 3), round(float(rs[seg_right].mean()), 3))

# Leave-one-out CV for candidate models (honest out-of-sample error)
def loo(model_fn):
    errs = []
    for i in range(n):
        m = np.ones(n, bool); m[i] = False
        errs.append(model_fn(P[m], S[m], P[i]) - S[i])
    errs = np.array(errs)
    return float(np.sqrt(np.mean(errs**2))), float(np.median(np.abs(errs)))
def fit_lin(p, s, x): c = np.polyfit(p, s, 1); return np.polyval(c, x)
def fit_pow(p, s, x):
    c = curve_fit(f_pow, p, s, p0=[100, -0.5], maxfev=20000)[0]; return f_pow(x, *c)
def fit_quad(p, s, x): c = np.polyfit(p, s, 2); return np.polyval(c, x)
def fit_pw(p, s, x):
    # piecewise: choose segment by a breakpoint fixed at the observed jump midpoint
    bp = best["bp"]
    side = x < bp
    m = (p < bp) if side else (p >= bp)
    c = curve_fit(f_pow, p[m], s[m], p0=[100,-0.5], maxfev=20000)[0]
    return f_pow(x, *c)
cv = {
    "linear": loo(fit_lin), "power": loo(fit_pow), "quadratic": loo(fit_quad), "piecewise_power": loo(fit_pw)
}
for k, (rmse, mae) in cv.items():
    print(f"LOO-CV {k}: RMSE={rmse:.4f}, median|err|={mae:.4f}")

summary = dict(
    n=n, single_model_fits=results,
    breakpoint_kPa=best["bp"],
    piecewise=dict(left=dict(a=float(best["pl"][0]), m=float(best["pl"][1])),
                   right=dict(a=float(best["pr"][0]), m=float(best["pr"][1])),
                   sse=float(best["sse"])),
    loo_cv={k: dict(rmse=v[0], median_abs_err=v[1]) for k, v in cv.items()},
)
json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), indent=2)

# Plot
fig, ax = plt.subplots(1, 2, figsize=(12, 4.8))
xx = np.linspace(P.min(), P.max(), 400)
a = ax[0]
a.scatter(P, S, s=18, color="#222", label="data", zorder=3)
a.plot(xx, np.polyval(b, xx), "--", color="#999", label=f"linear (R²={results['linear']['R2']:.3f})")
a.plot(xx, f_pow(xx, *pp), color="#1f77b4", label=f"power law (R²={results['power']['R2']:.3f})")
xl = xx[xx < best["bp"]]; xr = xx[xx >= best["bp"]]
a.plot(xl, f_pow(xl, *bl_pow), color="#d62728", lw=2, label="piecewise power, low-P segment")
a.plot(xr, f_pow(xr, *br_pow), color="#2ca02c", lw=2, label="piecewise power, high-P segment")
a.axvline(best["bp"], color="#888", ls=":", label=f"breakpoint ≈ {best['bp']:.2f} kPa")
a.set_xlabel("Chamber pressure (kPa)"); a.set_ylabel("Flame speed (cm/s)")
a.set_title("Flame speed vs chamber pressure"); a.legend(fontsize=8); a.grid(alpha=0.3)
b2 = ax[1]
r_single = S - f_pow(P, *pp)
r_pw = np.where(seg_left, S - f_pow(P, *bl_pow), S - f_pow(P, *br_pow))
b2.axhline(0, color="#888", lw=0.8)
b2.scatter(P, r_single, s=16, color="#1f77b4", label="residual: single power law")
b2.scatter(P, r_pw, s=16, color="#d62728", marker="x", label="residual: piecewise")
b2.axvline(best["bp"], color="#888", ls=":")
b2.set_xlabel("Chamber pressure (kPa)"); b2.set_ylabel("Residual (cm/s)")
b2.set_title("Residuals"); b2.legend(fontsize=8); b2.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(FIG, "flame_speed_vs_pressure.png"), dpi=150)
print("saved figure and summary")
