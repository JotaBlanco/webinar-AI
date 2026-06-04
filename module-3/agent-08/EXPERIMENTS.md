# EXPERIMENTS.md

Append-only log of approaches tried.

---

## E00 — V0 baseline (no changes)
- Rung: 0
- Hypothesis: establish the floor we're trying to beat.
- What I changed vs nothing: nothing — predict() passes through `yaw_rate_pred_rads`.
- Result (dev): pooled yaw RMSE 0.012934 rad/s, pooled CTE RMSE 163.83 m, n=1996 sim segments.
  Per-platform: Lightning 0.01633 / 157.5, Mach-E 0.01362 / 148.0, IONIQ-5 0.01770 / 247.5, Tesla 0 / 0.
  Bias-check: Lightning cte_drift 🚨 (+39.7 m), IONIQ-5 cte_drift 🚨 (-54.8 m); Mach-E ok.
- Verdict: baseline.
- Things this rules out: nothing yet.

## E01 — Rung-0 KS + understeer + first-order lag + platform-gated per-segment δ₀
- Rung: 0
- Hypothesis: replicating the top-tier m3 recipe (anti-patterns.md § "Legal cousin") should drop pooled yaw ~55% and pooled CTE ~65% on this data.
- What I changed vs E00: steady-state `yr_ss = v·(δ-δ₀)·g / (L_eff + K_us·v²)` with per-platform `{g, L_eff, K_us, τ}`; first-order lag with τ; **per-segment δ₀ from straight-row median of delta_road_rad on Mach-E and IONIQ-5** (gate: `|yr_v0|<0.03 ∧ v>5 m/s`, min 50 rows, fallback otherwise); **global δ₀ on Lightning** per the bias-spread gate; Tesla passthrough.
  Coefficients: Lightning g=0.863, L_eff=3.26, K_us=0.00350, τ=0.060, δ₀=0.00133. Mach-E g=0.891, L_eff=2.22, K_us=0.00150, τ=0.069, fallback δ₀=-0.0001. IONIQ-5 g=0.938, L_eff=2.887, K_us=0.00289, τ=0.062, fallback δ₀=0.
- Result (dev): yaw 0.012934 → **0.005874 (-54.6%)**; CTE 163.83 → **56.81 (-65.3%)**.
  Per-platform yaw: Lightning 0.00566, Mach-E 0.00859, IONIQ-5 0.00766, Tesla 0.
  Per-platform CTE: Lightning 62.2, Mach-E 98.7, IONIQ-5 69.5, Tesla 0.
  Bias-check: Lightning ok now; Mach-E cte_drift 🚨 (-22 m); IONIQ-5 cte_drift ⚠️ (-11.6 m).
- Verdict: keep — this is the shipped model.
- Things this rules out: confirms the platform-gated per-segment δ₀ recipe carries the weight on this dataset; Mach-E has residual signed CTE drift suggesting heterogeneous route bias still uncorrected — a route-level δ₀ refinement or per-platform refit of g/L_eff would likely move it further.

## E02 — Rung-1 climb attempt: linear dynamic single-track with slip angles (uncalibrated)
- Rung: 1
- Hypothesis: replace the V0 steady-state+lag heuristic with a principled (vy, yr) ODE driven by linear lateral tyres. Per AGENTS.md § "On exploration", a rung-1 attempt is required regardless of shipping.
- What I changed vs E01: implemented minimum-viable rung-1 from `references/dynamics-formulations.md` § "Rung 1" — two states (vy, yr), front/rear slip angles, linear F_y = C_α·α tyre, sub-stepped Euler (5×, dt cap 20 ms), vx clamp 5 m/s. Parameters pulled from `code/parameters.py` carParams (Mach-E only had a class; IONIQ-5 used approximate carParams). Lightning + Tesla left at V0 passthrough to isolate the climb. **No fitted coefficients** — carParams used as-is.
- Result (dev): pooled yaw RMSE **0.018679 (+44% WORSE than V0)**, pooled CTE 137.06 (slightly better than V0 163.83 but much worse than E01).
  Per-platform yaw: Mach-E 0.01562 (vs V0 0.01362, E01 0.00859 → rung-1 worse than V0); IONIQ-5 0.02752 (vs V0 0.01770, E01 0.00766 → rung-1 much worse than V0).
- Verdict: revert. Fall back to E01.
- Things this rules out / learnt: openpilot carParams `C_α` values are **not** ground truth for this dataset (anti-patterns.md § "Trusting tool-supplied bounds and priors" warned this). Without scipy-fitting `C_αf` (or both stiffnesses) per platform, an uncalibrated dynamic ST overshoots steady-state gain — the model is structurally richer but the numerical regime is wrong. A serious rung-1 attempt would need: (1) per-platform `C_αf` fit, (2) probable additional `C_αr` scale, (3) re-evaluation against E01. Cohort evidence so far: rung-1 doesn't pay *without* per-platform stiffness calibration. With the recipe in `code/parameters.py` as-is, rung 0 + δ₀ dominates rung 1.

---

## Summary

Shipped: E01 (rung 0 + platform-gated per-segment δ₀). Pooled yaw **-54.6%** vs V0, pooled CTE **-65.3%** vs V0.

Climb attempt logged: E02 (rung 1, uncalibrated linear dynamic ST). Underperforms E01 because carParams stiffness values are off for this data and a `C_αf` fit was outside the budget.
