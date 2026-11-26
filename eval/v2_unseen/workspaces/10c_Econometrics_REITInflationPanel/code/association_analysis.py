"""Association analysis: quarterly REIT index return vs. inflation (YoY).

numpy/scipy only (statsmodels is not installed in this environment).
Reads data/reit_macro_quarterly.csv read-only; prints results to stdout.
"""
import csv
import os
import numpy as np
from scipy import stats

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data", "reit_macro_quarterly.csv")

rows = list(csv.DictReader(open(DATA)))
q = np.array([int(r["quarter"]) for r in rows])
pi = np.array([float(r["inflation_yoy"]) for r in rows])   # inflation, YoY, %
rr = np.array([float(r["reit_index_return"]) for r in rows])  # REIT index return (units undocumented)
n = len(q)
print(f"N = {n} quarters (index {q.min()}..{q.max()}); no date column provided")
print("\n== Descriptives ==")
for name, x in [("inflation_yoy", pi), ("reit_index_return", rr)]:
    print(f"{name:18s} mean={x.mean():.4f} sd={x.std(ddof=1):.4f} "
          f"min={x.min():.4f} median={np.median(x):.4f} max={x.max():.4f}")
print(f"AR(1) inflation  rho1={np.corrcoef(pi[:-1], pi[1:])[0,1]:.3f}")
print(f"AR(1) REIT       rho1={np.corrcoef(rr[:-1], rr[1:])[0,1]:.3f}")


def fisher_ci(r, n, alpha=0.05):
    z = np.arctanh(r); se = 1 / np.sqrt(n - 3); c = stats.norm.ppf(1 - alpha/2)
    return np.tanh(z - c*se), np.tanh(z + c*se)


def newey_west_ols(y, X, lags):
    """OLS with Newey-West (Bartlett kernel) HAC standard errors."""
    X = np.column_stack([np.ones(len(y)), X])
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ X.T @ y
    e = y - X @ b
    T, k = X.shape
    S = (X * e[:, None]).T @ (X * e[:, None]) / T
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = (X[L:] * e[L:, None]).T @ (X[:-L] * e[:-L, None]) / T
        S += w * (G + G.T)
    V = XtX_inv @ (T * S) @ XtX_inv * (T / (T - k))
    se = np.sqrt(np.diag(V))
    t = b / se
    p = 2 * (1 - stats.t.cdf(np.abs(t), df=T - k))
    r2 = 1 - (e @ e) / ((y - y.mean()) @ (y - y.mean()))
    return b, se, p, r2


print("\n== Contemporaneous association (same quarter) ==")
r_p, p_p = stats.pearsonr(pi, rr)
r_s, p_s = stats.spearmanr(pi, rr)
lo, hi = fisher_ci(r_p, n)
print(f"Pearson r={r_p:.3f} (95% Fisher CI [{lo:.3f}, {hi:.3f}]) p={p_p:.4g}  [iid p-value; see HAC/bootstrap below]")
print(f"Spearman rho={r_s:.3f} p={p_s:.4g}")

# Block bootstrap CI (circular, block length 4) to respect serial dependence
rng = np.random.default_rng(20260101)
B, L = 10000, 4
boot = np.empty(B)
for b_ in range(B):
    starts = rng.integers(0, n, size=int(np.ceil(n / L)))
    idx = np.concatenate([(s + np.arange(L)) % n for s in starts])[:n]
    boot[b_] = np.corrcoef(pi[idx], rr[idx])[0, 1]
print(f"Circular block-bootstrap (L=4, B={B}) 95% CI for Pearson r: "
      f"[{np.percentile(boot,2.5):.3f}, {np.percentile(boot,97.5):.3f}]")

# Permutation p-value (ignores serial dependence; reported only as a reference)
perm = np.array([np.corrcoef(rng.permutation(pi), rr)[0, 1] for _ in range(B)])
print(f"Permutation p (iid, reference only) = {np.mean(np.abs(perm) >= abs(r_p)):.4g} (B={B}; 0 means < 1/B)")

print("\n== OLS: REIT return on inflation (Newey-West HAC, lag=4) ==")
b, se, p, r2 = newey_west_ols(rr, pi, lags=4)
print(f"const={b[0]:.4f} (se {se[0]:.4f})  beta_infl={b[1]:.4f} (se {se[1]:.4f}, p={p[1]:.3g}) R2={r2:.3f}")
ci = b[1] + np.array([-1, 1]) * stats.t.ppf(0.975, n-2) * se[1]
print(f"beta 95% CI [{ci[0]:.4f}, {ci[1]:.4f}]")

print("\n== Lead/lag cross-correlations (corr(inflation_{t-k}, REIT_t)) ==")
for k in range(-4, 5):
    if k >= 0:
        x, y = pi[:n-k], rr[k:]
    else:
        x, y = pi[-k:], rr[:n+k]
    r_k = np.corrcoef(x, y)[0, 1]
    print(f"k={k:+d}  n={len(x):2d}  r={r_k:+.3f}")

print("\n== Lagged regression: REIT_t on inflation_{t-1} (HAC lag=4) ==")
b1, se1, p1, r21 = newey_west_ols(rr[1:], pi[:-1], lags=4)
print(f"beta_lag1={b1[1]:.4f} (se {se1[1]:.4f}, p={p1[1]:.4g}) R2={r21:.3f}")

print("\n== Regime split: inflation >= 3.0% vs < 3.0% ==")
hi_m = pi >= 3.0
print(f"n_high={hi_m.sum()} mean REIT={rr[hi_m].mean():.4f} | n_low={(~hi_m).sum()} mean REIT={rr[~hi_m].mean():.4f}")
t_w, p_w = stats.ttest_ind(rr[hi_m], rr[~hi_m], equal_var=False)
print(f"Welch t={t_w:.3f} p={p_w:.4g} (iid)")
print(f"Median REIT high={np.median(rr[hi_m]):.4f} low={np.median(rr[~hi_m]):.4f}; "
      f"Mann-Whitney p={stats.mannwhitneyu(rr[hi_m], rr[~hi_m]).pvalue:.4g}")

print("\n== Sub-sample stability (first vs second half) ==")
h = n // 2
for lab, s in [("first half", slice(0, h)), ("second half", slice(h, n))]:
    r_h, p_h = stats.pearsonr(pi[s], rr[s])
    print(f"{lab:12s} n={len(pi[s])} r={r_h:+.3f} p={p_h:.4g}")

print("\n== Influence / robustness ==")
# leave-one-out correlation range
loo = np.array([np.corrcoef(np.delete(pi, i), np.delete(rr, i))[0, 1] for i in range(n)])
i_min, i_max = loo.argmin(), loo.argmax()
print(f"Leave-one-out r range: [{loo.min():.3f} (drop q{q[i_min]}), {loo.max():.3f} (drop q{q[i_max]})]")
# Cook's distance for OLS
X = np.column_stack([np.ones(n), pi])
H = X @ np.linalg.inv(X.T @ X) @ X.T
e = rr - H @ rr
s2 = e @ e / (n - 2)
cook = (e**2 / (2 * s2)) * np.diag(H) / (1 - np.diag(H))**2
top = np.argsort(cook)[::-1][:3]
print("Top Cook's D: " + ", ".join(f"q{q[i]}={cook[i]:.3f}" for i in top))
# Spearman without the highest-leverage point
keep = np.ones(n, bool); keep[top[0]] = False
r_wo, p_wo = stats.pearsonr(pi[keep], rr[keep])
print(f"Pearson r dropping q{q[top[0]]}: {r_wo:+.3f} (p={p_wo:.4g})")

print("\n== Power note ==")
# minimal detectable |r| at alpha=0.05 two-sided, iid, n
tc = stats.t.ppf(0.975, n - 2)
print(f"With n={n}, iid, the 5% two-sided critical |r| is {tc/np.sqrt(tc**2 + n - 2):.3f}")
