"""Beverage cooling analysis (run with: python3 -I code/fit_cooling.py).

Part A: single-process fits on all 200 points (Newton variants, two-exponential, power-law).
Part B: diagnosis of the residuals -> two abrupt discontinuities (t~80 jump up, t~121 drop).
Part C: event-aware Newton model: T(t) = Ta + (T0-Ta)e^{-kt} + sum_j J_j * H(t - t_j) * e^{-k(t - t_j)}
        with change-points t_j located by scanning and jump amplitudes J_j fitted.
        Also refits Newton on the clean pre-event window and checks the post-event window.
Outputs: out/fit_log (stdout, saved by shell), out/fit_summary.json, outputs/residuals.csv, outputs/fit_plot.svg
"""
import json, os
import numpy as np
from scipy.optimize import curve_fit

WS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(WS, "out"); OUTPUTS = os.path.join(WS, "outputs")
os.makedirs(OUT, exist_ok=True); os.makedirs(OUTPUTS, exist_ok=True)

raw = np.genfromtxt(os.path.join(WS, "data", "beverage_temperature_series.csv"), delimiter=",", names=True)
t = raw["time_min"].astype(float); y = raw["temperature_c"].astype(float); n = len(t)
print(f"N={n}, t in [{t.min():.0f},{t.max():.0f}] min, T in [{y.min():.3f},{y.max():.3f}] C, uniform 1-min steps")

def stats(res, k_params):
    rss = float(np.sum(res**2)); nn = len(res)
    return dict(rmse=float(np.sqrt(rss/nn)), rss=rss,
                aic=float(nn*np.log(rss/nn)+2*k_params), bic=float(nn*np.log(rss/nn)+k_params*np.log(nn)),
                max_abs_resid=float(np.max(np.abs(res))),
                lag1_autocorr=float(np.corrcoef(res[:-1], res[1:])[0, 1]))

# ---------------- Part A: smooth models on full series ----------------
def m_newton(t, Ta, T0, k): return Ta + (T0-Ta)*np.exp(-k*t)
def m_newton_T0fixed(t, Ta, k): return Ta + (y[0]-Ta)*np.exp(-k*t)
def m_2exp(t, Ta, A, k1, B, k2): return Ta + A*np.exp(-k1*t) + B*np.exp(-k2*t)
def m_power(t, Ta, T0, b, p): return Ta + (T0-Ta)*(1+b*t)**(-p)

A_models = {
    "A1_newton_Ta_T0_k": (m_newton, [22, 85, 0.03], ([-50, 0, 1e-6], [60, 200, 2]), ["Ta","T0","k"]),
    "A2_newton_T0fixed": (m_newton_T0fixed, [22, 0.03], ([-50, 1e-6], [60, 2]), ["Ta","k"]),
    "A3_two_exponential": (m_2exp, [22, 40, 0.1, 20, 0.01], ([-50,-200,1e-6,-200,1e-6],[60,200,5,200,5]), ["Ta","A","k1","B","k2"]),
    "A4_power_law_excess": (m_power, [22, 85, 0.05, 1.0], ([-50,0,1e-6,1e-3],[60,200,10,10]), ["Ta","T0","b","p"]),
}
summary = {"A_smooth_full": {}}
print("\n== Part A: smooth models, all 200 points ==")
for name, (f, p0, bnd, pn) in A_models.items():
    popt, pcov = curve_fit(f, t, y, p0=p0, bounds=bnd, maxfev=200000)
    se = np.sqrt(np.diag(pcov))
    st = stats(y - f(t, *popt), len(popt))
    summary["A_smooth_full"][name] = dict(params=dict(zip(pn, map(float, popt))), stderr=dict(zip(pn, map(float, se))), **st)
    print(f"{name}: " + ", ".join(f"{a}={b:.5g}+/-{c:.2g}" for a, b, c in zip(pn, popt, se)))
    print(f"   RMSE={st['rmse']:.4f} AIC={st['aic']:.1f} BIC={st['bic']:.1f} max|r|={st['max_abs_resid']:.3f} lag1-acf(res)={st['lag1_autocorr']:.3f}")

# ---------------- Part B: where do the residuals come from? ----------------
print("\n== Part B: first differences (raw) ==")
dy = np.diff(y)
# robust outlier screen: compare each first difference with a smooth local trend (median of neighbours)
local = np.array([np.median(dy[max(0, i-3):i+4]) for i in range(len(dy))])
dev = dy - local
ev = np.where(np.abs(dev) > 0.5)[0]
print("first-difference deviations > 0.5 C/min from local median (index i means y[i+1]-y[i]):")
for i in ev:
    print(f"  step t={i}->{i+1}: dy={dy[i]:+.3f}, local trend={local[i]:+.3f}, deviation={dev[i]:+.3f}")
print(f"smoothness: sd of 2nd differences excluding events = {np.std(np.delete(np.diff(y,2), np.r_[ev-1, ev]) ):.4f}")

# ---------------- Part C: event-aware Newton model (a misspecified alternative: decaying step, NOT the generator) ----------------
# Change points: first post-event reading index (event lies between t_j-1 and t_j)
evt = [int(ev[0]+1), int(ev[1]+1)]  # 80 and 121
print(f"\n== Part C: event-aware Newton model, change points at t={evt} ==")
def H(tt, tj): return (tt >= tj).astype(float)
def m_event(tt, Ta, T0, k, J1, J2):
    base = Ta + (T0-Ta)*np.exp(-k*tt)
    e1 = J1*H(tt, evt[0])*np.exp(-k*(tt-evt[0]))
    e2 = J2*H(tt, evt[1])*np.exp(-k*(tt-evt[1]))
    return base + e1 + e2
popt, pcov = curve_fit(m_event, t, y, p0=[20, 83, 0.01, 5, -7], maxfev=200000)
se = np.sqrt(np.diag(pcov))
res_ev = y - m_event(t, *popt)
stE = stats(res_ev, 5)
for nm, v, s in zip(["Ta","T0","k","J1(jump@80)","J2(drop@121)"], popt, se):
    print(f"  {nm:>13s} = {v:.5g} +/- {s:.2g}")
print(f"  tau=1/k={1/popt[2]:.1f} min; RMSE={stE['rmse']:.4f}, max|r|={stE['max_abs_resid']:.4f}, lag1-acf={stE['lag1_autocorr']:.3f}")
summary["C_event_newton"] = dict(change_points=evt, params=dict(zip(["Ta","T0","k","J1","J2"], map(float, popt))),
                                 stderr=dict(zip(["Ta","T0","k","J1","J2"], map(float, se))), **stE)

# Robustness: scan change-point locations near the detected ones (+/-3 min), refit, report best RSS
best = None
for c1 in range(77, 84):
    for c2 in range(118, 125):
        evt_try = [c1, c2]
        def f_try(tt, Ta, T0, k, J1, J2, _e=evt_try):
            return (Ta + (T0-Ta)*np.exp(-k*tt)
                    + J1*(tt >= _e[0])*np.exp(-k*(tt-_e[0])) + J2*(tt >= _e[1])*np.exp(-k*(tt-_e[1])))
        try:
            p, _ = curve_fit(f_try, t, y, p0=popt, maxfev=50000)
        except Exception:
            continue
        rss = float(np.sum((y-f_try(t, *p))**2))
        if best is None or rss < best[0]:
            best = (rss, c1, c2, p)
print(f"  change-point scan (+/-3 min): best at t={best[1]},{best[2]} RSS={best[0]:.4f} (fixed-cp RSS={stE['rss']:.4f})")
summary["C_event_newton"]["scan_best_changepoints"] = [best[1], best[2]]

# ---------------- Part D: clean-window Newton (pre-event) and post-window check ----------------
print("\n== Part D: Newton fitted only to clean windows ==")
for lo, hi, label in [(0, 80, "pre-event t<80"), (81, 121, "between events 81<=t<121"), (121, 200, "post-event t>=121"), (0, 200, "whole series excluding both event readings")]:
    sel = (t >= lo) & (t < hi)
    if label.startswith("whole"):
        sel = ~np.isin(np.arange(n), [evt[0], evt[1]])
    try:
        p, pc = curve_fit(m_newton, t[sel], y[sel], p0=[20, y[sel][0], 0.01], bounds=([-50, 0, 1e-6], [60, 200, 2]), maxfev=200000)
        se_ = np.sqrt(np.diag(pc)); st_ = stats(y[sel]-m_newton(t[sel], *p), 3)
        print(f"  {label:<45s} n={sel.sum():3d} Ta={p[0]:7.3f}+/-{se_[0]:.2f} T0={p[1]:7.3f} k={p[2]:.5f}+/-{se_[2]:.5f} "
              f"tau={1/p[2]:6.1f} RMSE={st_['rmse']:.4f} lag1-acf={st_['lag1_autocorr']:+.3f}")
        summary.setdefault("D_clean_windows", {})[label] = dict(n=int(sel.sum()), Ta=float(p[0]), T0=float(p[1]), k=float(p[2]), tau=float(1/p[2]), **st_)
    except Exception as e:
        print(f"  {label}: failed ({e})")

# Residual of the event model, by segment (should be white noise if model is adequate)
print("\nEvent-model residual by segment (mean, sd):")
for lo, hi in [(0, 80), (80, 121), (121, 200)]:
    s = (t >= lo) & (t < hi)
    print(f"  t in [{lo},{hi}): mean={res_ev[s].mean():+.4f} sd={res_ev[s].std():.4f}")

# Ambient sensitivity for the event model (Ta fixed on a grid)
print("\nAmbient sensitivity (event model, Ta fixed):")
sens = {}
for Ta_f in [15.0, 18.0, 20.0, 22.0, 24.0, 26.0]:
    g = lambda tt, T0_, k_, J1_, J2_: m_event(tt, Ta_f, T0_, k_, J1_, J2_)
    p, _ = curve_fit(g, t, y, p0=[83, popt[2], popt[3], popt[4]], maxfev=100000)
    rr = y - g(t, *p)
    sens[str(Ta_f)] = dict(T0=float(p[0]), k=float(p[1]), J1=float(p[2]), J2=float(p[3]), rmse=float(np.sqrt(np.mean(rr**2))))
    print(f"  Ta={Ta_f:5.1f}: T0={p[0]:.3f} k={p[1]:.5f} tau={1/p[1]:.1f} J1={p[2]:+.3f} J2={p[3]:+.3f} RMSE={np.sqrt(np.mean(rr**2)):.4f}")
summary["ambient_sensitivity_event_model"] = sens

# Derived quantities
Ta_e, T0_e, k_e = popt[0], popt[1], popt[2]
print(f"\nDerived (event model): half-life of excess = {np.log(2)/k_e:.1f} min; "
      f"fraction of initial excess remaining at t=199 = {np.exp(-k_e*199):.4f}")

# ---------------- Part E: piecewise-ambient Newton (preferred) ----------------
# Newton curve per segment: T = Ta_j + (T0 - Ta_j) e^{-k t}, shared T0 and k, Ta_j piecewise on the
# three segments [0,80), [80,121), [121,end). Segment boundaries are the detected event indices.
print("\n== Part E: piecewise-ambient Newton (shared T0,k; segment Ta_j) ==")
seg_id = np.where(t < evt[0], 0, np.where(t < evt[1], 1, 2))
def m_piece(tt, Ta1, Ta2, Ta3, T0_, k_):
    Tas = np.array([Ta1, Ta2, Ta3])[np.where(tt < evt[0], 0, np.where(tt < evt[1], 1, 2))]
    return Tas + (T0_ - Tas)*np.exp(-k_*tt)
pE, cE = curve_fit(m_piece, t, y, p0=[25, 34, 25, 85, 0.0115], maxfev=200000)
seE = np.sqrt(np.diag(cE))
resE = y - m_piece(t, *pE)
stEE = stats(resE, 5)
names = ["Ta_seg1(t<80)","Ta_seg2(80<=t<121)","Ta_seg3(t>=121)","T0","k"]
for nm, v, s in zip(names, pE, seE):
    print(f"  {nm:>20s} = {v:.6f} +/- {s:.2g}")
print(f"  tau=1/k={1/pE[4]:.2f} min; RMSE={stEE['rmse']:.5f}, max|r|={stEE['max_abs_resid']:.5f}, lag1-acf={stEE['lag1_autocorr']:+.3f}")
kE = pE[4]
jump80 = (pE[1]-pE[0])*(1-np.exp(-kE*evt[0]))
jump121 = (pE[2]-pE[1])*(1-np.exp(-kE*evt[1]))
print(f"  implied discontinuity at t=80: {jump80:+.3f} C (observed deviation +5.383)")
print(f"  implied discontinuity at t=121: {jump121:+.3f} C (observed deviation -6.756)")
for lo, hi in [(0, 80), (80, 121), (121, 200)]:
    s = (t >= lo) & (t < hi)
    print(f"  residual t in [{lo},{hi}): mean={resE[s].mean():+.5f} sd={resE[s].std():.5f}")
# Fix T0 at the first reading (85.0) and check it doesn't cost fit quality
pE2, cE2 = curve_fit(lambda tt, a1, a2, a3, k_: m_piece(tt, a1, a2, a3, y[0], k_), t, y, p0=[25, 34, 25, 0.0115], maxfev=200000)
rE2 = y - m_piece(t, pE2[0], pE2[1], pE2[2], y[0], pE2[3])
print(f"  with T0 fixed at y[0]={y[0]:.1f}: Ta=({pE2[0]:.4f},{pE2[1]:.4f},{pE2[2]:.4f}) k={pE2[3]:.6f} RMSE={np.sqrt(np.mean(rE2**2)):.5f}")
summary["E_piecewise_ambient_newton"] = dict(params=dict(zip(["Ta1","Ta2","Ta3","T0","k"], map(float, pE))),
                                              stderr=dict(zip(["Ta1","Ta2","Ta3","T0","k"], map(float, seE))),
                                              tau_min=float(1/kE), implied_jump_t80=float(jump80), implied_jump_t121=float(jump121),
                                              T0fixed_params=dict(zip(["Ta1","Ta2","Ta3","k"], map(float, pE2))),
                                              **stEE)
pE_fit = m_piece(t, *pE)

# ---------------- write outputs ----------------
with open(os.path.join(OUTPUTS, "residuals.csv"), "w") as fh:
    fh.write("time_min,temperature_c,pred_piecewise_E,resid_piecewise_E,pred_A1_newton,resid_A1_newton\n")
    pA1 = m_newton(t, *summary["A_smooth_full"]["A1_newton_Ta_T0_k"]["params"].values())
    for i in range(n):
        fh.write(f"{t[i]:.0f},{y[i]:.3f},{pE_fit[i]:.5f},{resE[i]:+.5f},{pA1[i]:.5f},{y[i]-pA1[i]:+.5f}\n")
with open(os.path.join(OUT, "fit_summary.json"), "w") as fh:
    json.dump(summary, fh, indent=2)

# ---------------- plot (plain SVG: PIL is missing so matplotlib is unavailable) ----------------
W, Hh, L, R, Tp, Bt = 900, 520, 70, 20, 20, 50
def xs(v): return L + (v/200.0)*(W-L-R)
def ys(v): return Tp + (1-(v-10)/(90-10))*(Hh-Tp-Bt)
def poly(xarr, yarr, col, dash=""):
    pts = " ".join(f"{xs(a):.1f},{ys(b):.1f}" for a, b in zip(xarr, yarr))
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline fill="none" stroke="{col}" stroke-width="1.6"{d} points="{pts}"/>'
tt = np.linspace(0, 199, 800)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{Hh}" font-family="sans-serif" font-size="12">',
       f'<rect width="{W}" height="{Hh}" fill="white"/>',
       f'<line x1="{L}" y1="{Hh-Bt}" x2="{W-R}" y2="{Hh-Bt}" stroke="black"/>',
       f'<line x1="{L}" y1="{Tp}" x2="{L}" y2="{Hh-Bt}" stroke="black"/>']
for v in range(0, 201, 20):
    svg.append(f'<text x="{xs(v)-8:.1f}" y="{Hh-Bt+16}">{v}</text>')
for v in range(10, 91, 10):
    svg.append(f'<text x="{L-38}" y="{ys(v)+4:.1f}">{v}</text>')
svg.append(f'<text x="{W/2-40}" y="{Hh-10}">time (min)</text>')
svg.append(f'<text x="8" y="{Tp+10}">T (°C)</text>')
svg.append(poly(tt, m_piece(tt, *pE), "#1f77b4"))
svg.append(poly(tt, m_newton(tt, *summary["A_smooth_full"]["A1_newton_Ta_T0_k"]["params"].values()), "#d62728", "6,4"))
for a, b in zip(t, y):
    svg.append(f'<circle cx="{xs(a):.1f}" cy="{ys(b):.1f}" r="2.2" fill="black"/>')
svg.append(f'<text x="{W-330}" y="{Tp+14}" fill="#1f77b4">— piecewise-ambient Newton (preferred)</text>')
svg.append(f'<text x="{W-330}" y="{Tp+30}" fill="#d62728">-- single Newton, all points</text>')
svg.append(f'<text x="{W-330}" y="{Tp+46}">● data</text>')
svg.append("</svg>")
with open(os.path.join(OUTPUTS, "fit_plot.svg"), "w") as fh:
    fh.write("\n".join(svg))
print("\nWrote out/fit_summary.json, outputs/residuals.csv, outputs/fit_plot.svg")
