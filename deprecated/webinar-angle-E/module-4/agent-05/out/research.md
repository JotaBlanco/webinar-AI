# Phase 1 — Research

## Platforms available
- `FORD_MUSTANG_MACH_E_MK1` — 315 segments, 913,626 samples, `yaw_rate_meas_rads` present (truth).
- `FORD_F_150_LIGHTNING_MK1` — 230 segments, 667,141 samples, truth present.
- `TESLA_MODEL_3` — present in tree but no truth channel (out of scope).

## Schema (Ford sim.csv)
Cols include `t_s, delta_road_rad, v_mps, yaw_rate_meas_rads, yaw_rate_pred_rads, yaw_rate_resid_rads`. dt ≈ 0.02 s (50 Hz). No NaNs in residual.

## Baseline RMSE (column as-is, no preprocessing)
| platform | overall | straight | steady | transient |
|---|---|---|---|---|
| Mach-E | 0.01613 | 0.00877 | 0.03028 | 0.05121 |
| Lightning | 0.02037 | 0.00899 | 0.03566 | 0.04846 |

Regime mask used: straight `|δ|<0.01`, steady `|δ|≥0.01 ∧ |dδ/dt|<0.05`, transient `|δ|≥0.01 ∧ |dδ/dt|≥0.05`.

## Anomalies / observations
- Mean residual on straight-line samples is markedly **positive** (~+0.012 rad/s on first segment) — looks like a per-segment yaw-gyro bias / sign offset that V1 should mostly remove. Straight-line RMSE is dominated by this DC offset, not noise.
- Both platforms include `v_mps` minima of 0.0 — Linear-ST will need a low-`v` fallback (`v_min = 2 m/s`) as the SKILL warns; Lightning has more stationary stretches, so V2/V3 risk is higher there.
- Transient cornering RMSE is the worst regime on both platforms (~5×10⁻² rad/s) — that's where V2/V3 should ideally win, but the linear ST is a *steady-state* gain, so a transient residual that *doesn't* shrink would be physically expected.
- Mach-E has cleaner straight-line numbers and ~30% more samples — easier to interpret attribution.

## Open questions before picking a ladder
- Will V1 (bias removal + canonical L) over-correct on Lightning given stationary stretches inflate the straight mask? — answer with per-segment bias.
- Does V3's `C_α` fit peg the upper bound? If so, V3 may regress on straight/steady vs V1.
- Is regime-comparison worth the extra section, or does the variant table already tell the story?
- Cross-platform: run both, or pick one to keep the report tight?
