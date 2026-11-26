# Numerical integration of a saturation-front traveling-wave ODE

## 1. Task interpretation and model

The task names a traveling-wave reduction for a porous-media saturation front but gives no equation, and `data/` does not exist in the workspace. I therefore chose a standard model and state it explicitly. Nothing here is taken from a dataset.

**PDE (1D two-phase flow, Buckley–Leverett flux with constant diffusion):**

    s_t + f(s)_x = ε s_xx,    f(s) = s² / (s² + M(1−s)²),    M = 2, ε = 0.01

**Traveling wave:** s(x,t) = u(ξ), ξ = x − c t, with u(−∞) = U_L = 0.75 and u(+∞) = U_R = 0.10.

**Reduction:** substituting and integrating once from −∞ (where u′, u″ → 0) gives

    ε u′  = G(u) := f(u) − f(U_L) − c (u − U_L)        (first-order autonomous ODE, used for integration)
    ε u″  = (f′(u) − c) u′                              (second-order form, used for verification)

**Speed:** the Rankine–Hugoniot condition c = (f(U_R) − f(U_L)) / (U_R − U_L) makes G(U_R) = 0 exactly. Here c = 1.2493028444.

**Admissibility:** the state pair was selected by scanning a grid of (U_L, U_R) pairs for Lax admissibility and a one-signed G between the states. The chosen pair satisfies f′(U_L) = 1.587 > c > f′(U_R) = 0.135 (Lax), and G has constant sign on the open interval (U_R, U_L) (checked on 2000 interior points). This guarantees a monotone heteroclinic orbit from U_L to U_R.

## 2. Integration method and settings

- **Solver:** `scipy.integrate.solve_ivp`, method DOP853 (explicit 8th-order Runge–Kutta, adaptive), rtol = 1e-11, atol = 1e-13 (scipy 1.18.1, numpy 2.5.4).
- **Phase condition:** u(0) = (U_L + U_R)/2 = 0.425. The orbit is integrated forward on [0, 60] and backward on [−60, 0]; both use the same RHS G(u)/ε.
- **Output grid:** dense output of the solver, sampled uniformly with spacing Δξ = 1e-4 on [−60, 60] (1 200 001 points). The transition layer has 10–90% width ≈ 0.043, so the grid must be much finer than the layer; a 0.01 grid was tried first and gave spurious second-derivative errors.
- **Runtime:** about 2.2×10⁴ RHS evaluations per run.

## 3. Verification: definition and results

Let u_h(ξ) be the computed profile. Define the **second-order ODE residual**

    r(ξ) = ε u″(ξ) − (f′(u(ξ)) − c) u′(ξ)

with u′ and u″ computed by second-order central finite differences of the sampled profile u_h (step h = 1e-4). This uses only the sampled values of u, not the first-order RHS, so it is an independent test of the reduction. Points where |u − U_L| ≤ 1e-6 or |u − U_R| ≤ 1e-6 (flat far-field tails) are excluded. The residual is normalized by the term scale max(|ε u″|, |(f′(u) − c) u′|). Measures:

| Measure | Value |
|---|---|
| Points used (interior, not in the tails) | 4 578 |
| max \|r\| | 1.23 × 10⁻³ |
| max \|ε u″\|, \|(f′−c) u′\| (scale) | 10.29 |
| max \|r\| / scale | 2.06 × 10⁻³ |
| relative L2 residual ‖r‖₂ / ‖(f′−c)u′‖₂ | 7.7 × 10⁻⁵ |
| first-order consistency max \|ε u′ − G(u)\| (FD-based) | 3.7 × 10⁻⁶ |

**Additional checks:**

1. **Far-field values:** u(−60) = 0.750000000000 and u(+60) = 0.100000000000, matching U_L and U_R.
2. **Monotonicity:** the largest upward step is 1.5 × 10⁻¹², i.e. round-off in the flat tails. The profile is monotone decreasing in ξ.
3. **Quadrature cross-check:** the closed-form representation ξ(u) = ε ∫_{u₀}^{u} dv / G(v) gives values that agree with the ODE solution to max error 7.9 × 10⁻¹⁰ over 201 points inside the transition layer.
4. **Tolerance convergence:** the maximum deviation of u from a reference solved with rtol = 1e-13 is 3.2 × 10⁻⁵ at rtol = 1e-6, 3.2 × 10⁻⁷ at rtol = 1e-8, and 3.0 × 10⁻⁹ at rtol = 1e-10. The error tracks the tolerance.

**Interpretation:** the relative residual of about 2 × 10⁻³ is the total of all error sources in the finite-difference second derivative (truncation at h = 1e-4 plus round-off). It is not separately decomposed. The first-order and quadrature checks show the orbit itself is accurate to about 1e-9 in ξ.

## 4. Findings

- With M = 2, ε = 0.01, U_L = 0.75, U_R = 0.10, the Lax shock speed is c = 1.249303. The computed profile is a monotone heteroclinic front connecting the two states.
- The 10–90% transition width is Δξ ≈ 0.0434, consistent with a diffusion-dominated layer of width O(ε / |G′|).
- The ODE solution satisfies the second-order reduced ODE to a relative residual of about 2 × 10⁻³ (relative L2 about 8 × 10⁻⁵), and agrees with the quadrature representation to about 8 × 10⁻¹⁰.

## 5. Limitations

- The model was chosen by me because the task specified none. A different traveling-wave reduction (e.g. with capillary pressure or a different flux) would change c and the profile. The methods here carry over directly.
- The verification residual is evaluated by finite differences. A more refined check would use an analytic u″ or a spectral derivative. The quadrature check is the sharper test of the orbit.
- Only one parameter set was run. No parameter sweep was performed.

## 6. Files

- `code/front_ode.py`: model, admissibility, DOP853 integration, residual, quadrature and convergence checks.
- `out/run_log.txt`: stdout of the final run.
- `outputs/summary.json`: all numerical results.
- `outputs/profile.csv`: computed profile u(ξ), subsampled to Δξ = 0.01 (full grid is Δξ = 1e-4).
