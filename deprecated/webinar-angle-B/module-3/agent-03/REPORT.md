# Module-3 / agent-03 (angle-B) — Lateral Fidelity, Mach-E MK1

**Platform:** `FORD_MUSTANG_MACH_E_MK1` (315 segments available; 120 used; 348 060 samples at 50 Hz).
**Operating contract:** speed-known, lateral-only. `v` and `δ` clamped to measured. Truth = `yaw_rate_meas_rads`. Tesla excluded (no IMU truth).
**Sign sanity:** `corr(δ_road, ψ̇_meas)` on cornering = **+0.752** — convention OK.
**Regime mask:** straight (`|δ|<0.01`) 300 928, steady 39 728, transient 7 404.

## Variant ladder (RMSE of `ψ̇_pred − ψ̇_meas` in rad/s)

| Variant | all | straight | steady | transient | Δ vs prev (all) |
|---|---:|---:|---:|---:|---:|
| V0 — KS baseline | 0.01550 | 0.00859 | 0.03197 | 0.05303 | — |
| V1 — KS + per-segment bias (estimated on straights) | 0.01429 | 0.00497 | 0.03247 | 0.05419 | -0.00121 |
| V2 — Linear ST, prior C_α + bias | 0.01570 | 0.00364 | 0.03641 | 0.06273 | +0.00141 (regression) |
| V3 — Linear ST, fit C_α + bias | 0.01536 | 0.00368 | 0.03552 | 0.06134 | -0.00034 |
| V4 — V3 + Ridge residual LOSO on [v, |a_y|, |δ|, sign(δ̇)] | 0.01251 | 0.00385 | 0.02875 | 0.04822 | -0.00284 |

**Marginal-drop accounting** (greedy / sequential, one DoF per rung). Sum = -0.00298; V0→V4 = -0.00299. Closes to 0.3% — well inside the 15% bound.

## Honest regression flags

- **V2 is a regression on `all`** (+0.00141). Linear ST with the openpilot prior `C_α` over-steers vs measured at the high-`|a_y|` end. Improvement on straights is the bias-soak, not ST geometry.
- **V3 `C_α` fit pegs the upper bound** (scale = 2.00, `C_αf` = 573 kN/rad, `C_αr` = 712 kN/rad). The linear-ST steady-state form is mis-specified for this fleet, not just the priors — pegging at the bound means "the model wants infinite stiffness", i.e. it wants KS back. The 0.00034 drop from V2 to V3 is cosmetic.
- **V4 is the only sizeable lateral win** but it is a residual launderer; LOSO is honest, but the structural ladder bought us almost nothing on cornering; the cornering residual is non-linear and we should escalate to ST with proper tyre saturation (Pacejka) before trusting a model upgrade.

## Painful absence / surprise

- **No `a_y` ladder row** — `a_y_pred_mps2` and `a_y_resid_mps2` present in CSV; consistency check between the two truth channels skipped.
- **Straight-line dominates sample mix** (86%). The `all` column flatters straight-line bias fixes; steady and transient are the meaningful regimes — on those, V1→V4 only halves the transient RMSE.

## Rule-prevented near-misses

- Almost ran on Tesla (more segments). Skill matrix forbade it — no truth.
- Almost used `delta_wheel_deg`. Factor of `i_s`=17 averted.
- Almost reported in-fold Ridge RMSE as V4. Switched to LOSO.

## Surprise

KS already does straight-line yaw rate to 0.009 rad/s and the ST upgrade buys *worse* on cornering — the team's prior `C_α` is not calibrated for these tyres on these roads, and the fit pegs the bound, the documented "linear-ST form is wrong, not just the priors" signal. The next honest rung is Pacejka, not another linear-ST variant.

Files: `tools/lateral_ladder.py`.
