# REPORT.md — webinar-angle-E / module-4 / agent-01

## 1. Platform & operating contract

- Platform: **`FORD_MUSTANG_MACH_E_MK1`** (skill default; 914,626 rows across 315 segments).
- `yaw_rate_meas_rads` is the measured truth channel (present on both Ford platforms, absent on Tesla).
- KS runs with `clamp_v_to_measured=True`, `clamp_delta_to_measured=True`. Speed-state agreement is zero by construction and is not the metric. `v` and `δ_road` are inputs; `yaw_rate_resid_rads = pred − meas` is the only metric.

## 2. Variant ladder (per-regime RMSE, rad/s)

| variant | overall | straight | steady | transient | marginal Δ overall | notes |
|---|---|---|---|---|---|---|
| V0 — baseline (column as-is) | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — | from `yaw_rate_resid_rads` in `sim.csv` |
| V1 — KS recalib + per-segment straight-line bias | **0.01469** | **0.00493** | 0.03168 | 0.05730 | -0.00143 (-8.9%) | bias removal almost entirely on straights |
| V2 — Linear ST, prior C_α (low-v KS fallback) | 0.01653 | 0.00701 | 0.03450 | 0.06234 | +0.00184 (regression) | regresses all three regimes vs V1 |
| V3 — Linear ST, fitted C_α | 0.01663 | 0.00700 | 0.03482 | 0.06266 | +0.00011 (regression) | fit degenerate (see dissent) |

Net V0→V3: **+0.00051 rad/s overall (got worse)**. Net V0→V1 (best): **-0.00143 rad/s (-8.9%)**.

## 3. Attribution

- Scheme: strict marginal, fixed order V0→V1→V2→V3. Marginal_i = RMSE(V_{i-1}) − RMSE(V_i).
- Marginal drops: V1 +0.00143, V2 −0.00184, V3 −0.00011. Sum = −0.00051. Total V0−V3 = −0.00051. **Mismatch 0.0%** (trivially within 15%; the check is by construction for overall RMSE).
- Per-regime contrast (sibling skill `regime-comparison`, negative = improvement vs V0):

| variant | Δ straight | Δ steady | Δ transient | dominant regime |
|---|---|---|---|---|
| V1 | -0.00384 | -0.00005 | +0.00050 | straight |
| V2 | -0.00176 | +0.00276 | +0.00555 | transient (regression) |
| V3 | -0.00177 | +0.00309 | +0.00586 | transient (regression) |

- V1 earns its entire win on the **straight** regime (per-segment yaw-gyro bias removal).
- V2 and V3 *help* on straights (smaller than V1's straight-line help) but *hurt* on steady and transient — they regress where the modelling change was supposed to pay off.

## 4. Regression flags

- **V2 vs V1, all regimes.** Linear-ST with openpilot prior C_α (286,551 / 355,912 N/rad) under-yaws relative to measured at the Mach-E's steering levels. Physical reason: the prior is generic, and tan(δ) → δ approximation drops nonlinear high-δ contribution that KS retains; on transients the linear model also misses lag.
- **V3 vs V2, all regimes.** Marginal further regression of ≈+1e-4 rad/s overall.
- **V3 fit is degenerate** — see Plan dissent. Treat V3 numbers as "model class V2 with optimiser confirmation", not "calibrated".

## 5. RPI provenance (which phase surfaced which decision)

- **Phase 1 (research.md):** flagged Lightning's 17% low-v share and persistent residual mean (-3.6e-3), which is why Mach-E was chosen in Phase 2 rather than blindly defaulted. Also surfaced the transient-vs-straight RMSE ratio (~6×) before any modelling.
- **Phase 2 (plan.md):** locked attribution scheme + 15% sum-check + out-of-scope list (V4 residual learner, nonlinear Pacejka, per-segment C_α fit, unclamping). The pre-commit to "report regressions honestly" made it natural to flag V2/V3 as regressions in Phase 3 instead of burying them.
- **Phase 3 (this report):** discovered the V3 optimiser degeneracy — the L-BFGS-B fit did not move from its `(1.5e5, 1.5e5)` initialisation. Not surfaceable in Phase 1 or 2.
- Net: the RPI split mostly bought *honesty about regressions*; it did not surface or repair the V3 fit degeneracy.

## 6. Plan dissent

- V3 L-BFGS-B returned exactly the init `(C_αf, C_αr) = (1.5e5, 1.5e5)` with `pegged=False`. The fit is degenerate — either the loss is flat at init scale or the finite-difference gradient underflowed. Per the AGENTS.md RPI contract I executed the locked plan as written and did **not** swap optimiser, add random restarts, or rescale parameters mid-Phase-3. A future run should:
  - normalise C_α by 1e5 before passing to L-BFGS-B, or
  - use a global method (Nelder–Mead with random restarts, or differential_evolution) over the bounded box, and
  - separately fit per-segment vs global to test whether the regression is a model-class issue or a calibration issue.
- Recommendation independent of dissent: **ship V1**, mothball V2/V3 until a non-degenerate fit can be produced, and consider a residual learner (out-of-skill V4) for the transient regime where physics-based models all degrade.
