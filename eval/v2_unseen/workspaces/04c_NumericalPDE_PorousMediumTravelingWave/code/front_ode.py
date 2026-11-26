"""
Traveling saturation front for a 1D two-phase porous-media model (fractional-flow / Buckley-Leverett
with diffusion).

PDE:      s_t + f(s)_x = EPS * s_xx,   f(s) = s^2 / (s^2 + M (1-s)^2),   M = 2 (mobility ratio)
Ansatz:   s(x,t) = u(xi), xi = x - c t,  u(-inf) = U_L,  u(+inf) = U_R
Reduction (integrate once from -inf, using u', u'' -> 0 there):
    EPS * u'  = G(u) := f(u) - f(U_L) - c (u - U_L)              (1st-order autonomous ODE)
    EPS * u'' = (f'(u) - c) u'                                    (2nd-order form, verification)
Rankine-Hugoniot: c = (f(U_R) - f(U_L)) / (U_R - U_L)  <=> G(U_R) = 0.

Integration: DOP853 (solve_ivp) on the 1st-order ODE, started at the phase point u(0) = (U_L+U_R)/2
and integrated forward and backward in xi.
Verification: (i) residual of the 2nd-order ODE, evaluated with spline derivatives of the computed
profile; (ii) agreement with the quadrature representation xi(u) = EPS * int dv/G(v);
(iii) far-field values reached; (iv) convergence under tolerance refinement.
"""
import json
import os
import sys

import numpy as np
from scipy.integrate import solve_ivp, quad
from scipy.interpolate import CubicSpline

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "out")
OUTPUTS = os.path.join(ROOT, "outputs")

M = 2.0
EPS = 0.01
U_L = 0.75
U_R = 0.10


def f(u):
    return u * u / (u * u + M * (1.0 - u) ** 2)


def fp(u):
    d = u * u + M * (1.0 - u) ** 2
    dd = 2.0 * u - 2.0 * M * (1.0 - u)
    return (2.0 * u * d - u * u * dd) / d ** 2


C = (f(U_R) - f(U_L)) / (U_R - U_L)  # Rankine-Hugoniot speed


def G(u):
    return f(u) - f(U_L) - C * (u - U_L)


def rhs(xi, y):
    return [G(y[0]) / EPS]


def integrate(rtol, atol, T=60.0, h=1e-4):
    """Integrate the 1st-order ODE from the phase point u(0)=(U_L+U_R)/2 forward (xi in [0,T])
    and backward (xi in [-T,0]) with DOP853; the profile is evaluated from the solver's dense
    output on a uniform grid of spacing h (the transition layer has width ~0.05, so the grid
    must be much finer than that). Returns (xi, u, nfev)."""
    u0 = 0.5 * (U_L + U_R)
    sf = solve_ivp(rhs, (0.0, T), [u0], method="DOP853", rtol=rtol, atol=atol, dense_output=True)
    sb = solve_ivp(rhs, (0.0, -T), [u0], method="DOP853", rtol=rtol, atol=atol, dense_output=True)
    assert sf.success and sb.success, (sf.message, sb.message)
    n = int(round(T / h))
    xf = np.linspace(0.0, T, n + 1)
    xb = np.linspace(-T, 0.0, n + 1)
    uf = sf.sol(xf)[0]
    ub = sb.sol(xb)[0]  # sb.sol is valid on [-T,0]
    xi = np.concatenate([xb[:-1], xf])
    u = np.concatenate([ub[:-1], uf])
    return xi, u, sf.nfev + sb.nfev


def second_order_residual(xi, u):
    """Residual of EPS*u'' - (f'(u)-C)*u' computed with central finite differences of the
    sampled profile only (no use of the RHS). Interior window avoids the far-field tails."""
    h = xi[1] - xi[0]
    up = np.gradient(u, h, edge_order=2)
    upp = np.gradient(up, h, edge_order=2)
    r = EPS * upp - (fp(u) - C) * up
    term = np.maximum(np.abs(EPS * upp), np.abs((fp(u) - C) * up))
    sel = np.abs(u - U_L) > 1e-6
    sel &= np.abs(u - U_R) > 1e-6  # exclude the flat far-field tails
    r1 = EPS * up - G(u)           # first-order consistency, also FD-based
    return dict(
        n_points_used=int(sel.sum()),
        max_abs_residual=float(np.max(np.abs(r[sel]))),
        max_abs_term=float(np.max(term[sel])),
        max_rel_residual=float(np.max(np.abs(r[sel]) / np.maximum(term[sel], 1e-300))),
        rel_L2_residual=float(np.linalg.norm(r[sel]) / np.linalg.norm(term[sel])),
        max_abs_first_order_residual=float(np.max(np.abs(r1[sel]))),
    )


def quadrature_check(xi, u):
    """xi(u) = EPS * int_{u0}^{u} dv / G(v) relative to the phase point; compare with ODE solution."""
    u0 = 0.5 * (U_L + U_R)
    # sample only inside the transition layer (flat tails carry no information)
    trans = np.where((u < U_L - 1e-4) & (u > U_R + 1e-4))[0]
    idx = trans[np.linspace(0, trans.size - 1, 201).astype(int)]
    errs = []
    for i in idx:
        if abs(xi[i]) < 1e-12 or abs(u[i] - U_R) < 1e-6 or abs(u[i] - U_L) < 1e-6:
            continue
        val, _ = quad(lambda v: 1.0 / G(v), u0, u[i], epsabs=1e-12, epsrel=1e-10, limit=400)
        errs.append(abs(EPS * val - xi[i]))
    return float(np.max(errs)), len(errs)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(OUTPUTS, exist_ok=True)
    info = dict(M=M, EPS=EPS, U_L=U_L, U_R=U_R, C=C, G_at_UR=float(G(U_R)), G_at_UL=float(G(U_L)))
    inside = np.linspace(U_R, U_L, 2001)[1:-1]
    gi = G(inside)
    info["G_one_sign_inside"] = bool(np.all(gi < 0) or np.all(gi > 0))
    info["Lax"] = bool(fp(U_L) > C > fp(U_R))
    info["fp_UL"] = float(fp(U_L))
    info["fp_UR"] = float(fp(U_R))
    print(json.dumps(info, indent=2))

    xi, u, nfev = integrate(rtol=1e-11, atol=1e-13, T=60.0, h=1e-4)
    print("\nMain run (rtol=1e-11, atol=1e-13): N=%d, nfev=%d" % (xi.size, nfev))
    print("u(-T)=%.12f (U_L=%.4f), u(+T)=%.12f (U_R=%.4f)" % (u[0], U_L, u[-1], U_R))
    print("max upward step (monotonicity violation): %.3e" % max(0.0, float(np.max(np.diff(u)))))

    res = second_order_residual(xi, u)
    print("2nd-order residual (interior):", json.dumps(res, indent=2))

    qerr, nq = quadrature_check(xi, u)
    print("quadrature check: max |xi_ODE(u) - xi_quad(u)| = %.3e over %d transition points" % (qerr, nq))

    # convergence under tolerance refinement, compared on a common grid via interpolation
    ref_xi, ref_u, _ = integrate(rtol=1e-13, atol=1e-15, T=60.0, h=1e-4)
    conv = {}
    for rtol in [1e-6, 1e-8, 1e-10]:
        xi_t, u_t, _ = integrate(rtol=rtol, atol=rtol * 1e-2, T=60.0, h=1e-4)
        conv["rtol=%g" % rtol] = float(np.max(np.abs(np.interp(ref_xi, xi_t, u_t) - ref_u)))
    print("max |u - u_ref| vs rtol (ref rtol=1e-13):", json.dumps(conv, indent=2))

    # half-width of transition: xi where u crosses 0.5*(U_L+U_R) is xi=0 by construction;
    # report 10%-90% width
    def xi_at(level):
        # monotone decreasing profile
        return float(np.interp(-level, -u, xi))
    # u decreases in xi: the 90%-level point (near U_L) lies at smaller xi than the 10%-level point
    w = xi_at(U_R + 0.1 * (U_L - U_R)) - xi_at(U_L - 0.1 * (U_L - U_R))
    print("10%%-90%% transition width in xi: %.6f" % w)

    sub = slice(None, None, 100)  # save every 1e-2 in xi (full grid is 1.2e6 points)
    np.savetxt(os.path.join(OUTPUTS, "profile.csv"), np.column_stack([xi[sub], u[sub]]),
               delimiter=",", header="xi,u", comments="", fmt="%.12e")
    summary = dict(info=info, residual=res, quadrature_max_err=qerr, convergence=conv,
                   transition_width_10_90=w, n_points=int(xi.size), grid_spacing=1e-4)
    with open(os.path.join(OUTPUTS, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print("\nWrote outputs/profile.csv and outputs/summary.json")


if __name__ == "__main__":

    main()
