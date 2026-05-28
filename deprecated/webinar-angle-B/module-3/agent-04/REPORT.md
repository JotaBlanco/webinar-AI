# Module-3 / agent-04 (angle-B) — Lateral fidelity, Mach-E MK1

## Headline

On **FORD_MUSTANG_MACH_E_MK1** (120-segment sample, 306 535 valid samples), the lateral residual under test is `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`. **A per-segment yaw-rate bias on straight-line samples — applied on top of KS — drops overall RMSE from 0.01326 to 0.01098 rad/s (-17%). Climbing the ladder to linear ST regresses.**

## Platform and clamping statement

- Platform: **FORD_MUSTANG_MACH_E_MK1** (Tesla excluded — no truth channel).
- `clamp_v_to_measured=True`, `clamp_delta_to_measured=True`. `v` and `δ` are inputs; `ψ̇` and `a_y` are predictions. Scored on `ψ̇` against `yaw_rate_meas_rads`.
- Sign sanity: `corr(δ_road, ψ̇_meas) = +0.937` on |δ| > 0.02 — convention correct.

## Variant ladder (RMSE of yaw-rate residual, rad/s)

Regime split: straight `|δ| < 0.01`; steady `|δ| ≥ 0.01 ∧ |δ̇| < 0.05`; transient `|δ| ≥ 0.01 ∧ |δ̇| ≥ 0.05`. Counts: all 306 535 / straight 267 811 / steady 31 811 / transient 6 913.

| Variant | all | straight | steady | transient | marginal (Δ from prev) |
|---|---:|---:|---:|---:|---:|
| V0 KS (baseline) | 0.01326 | 0.00936 | 0.02350 | 0.04310 | — |
| V1 KS + per-segment bias from straights | 0.01098 | 0.00494 | 0.02330 | 0.04360 | -0.00228 |
| V2 Linear ST, prior C_α | 0.01398 | 0.00777 | 0.02845 | 0.05102 | +0.00300 (regression) |
| V3 Linear ST, fit C_α + bias | 0.01192 | 0.00339 | 0.02680 | 0.05052 | -0.00206 |

V0 → V_last drop = -0.00133 rad/s. Sum-of-marginals = -0.00133 — exact match. Accounting scheme: cumulative-RMSE-drop per rung, `marginal = RMSE(V_{n-1}) − RMSE(V_n)`.

## What each change contributed

- **V1 (per-segment yaw-gyro bias from straight-line samples)** does essentially all the useful work: -0.00228 rad/s overall, -0.00442 rad/s on straights (which are 87% of samples). Cornering RMSE is unchanged at 0.02803 — a constant offset cannot help where the residual is signal-shaped.
- **V2 (linear ST, prior C_α)** is a **regression** in every regime. With Mach-E's openpilot priors, K_us comes out negative-ish/very small — the steady-state correction goes the wrong way at the speeds in this dataset relative to KS-and-bias.
- **V3 (ST with fit C_α + bias)** partially recovers the regression on straights (bias does it), but stays worse than V1 on every cornering regime. The optimiser **pegged C_αr at the 500 kN/rad upper bound** (α=1.40, C_αf=402k, C_αr=500k). Per the skill, pegging is itself the regression flag: the linear-ST functional form is wrong on this corpus, not the priors.

## Painful absence

No truth-channel transient acceleration to attribute residuals against. The transient bucket (6 913 samples, RMSE ~0.043–0.051 rad/s) is where the real gap lives, but with linear ST regressing there too, the next honest rung is non-linear tyre / slip model (Pacejka) or LOSO-CV residual learner — out of in-residual quick-fix scope. Also no per-segment IMU temperature / start-up channel.

## Near-misses

- Almost shipped V3 with α∈[0.3, 3.0]; fit went to α=3.0 (C_α ~860/1068 kN/rad), grossly unphysical. Re-bounding to skill-prescribed 50–500 kN/rad still pegs C_αr.
- Almost reported "+15% cornering improvement" by mixing V1 cornering RMSE with V0 straight RMSE before noticing the cornering bucket is unchanged V0↔V1.

## Surprise

KS, with a one-number-per-segment hack (mean straight-line offset), beats a properly-parameterised linear single-track on every regime including cornering. The story isn't "the model lacks slip" first — it's "the IMU has a per-route DC offset that swamps lateral-model error in the all-samples RMSE". Once that's removed, KS's remaining error is already what slip would address, and linear ST without a non-linear tyre cannot close it.

## Honest regression flags

- V2 worse than V1 in every regime (steady +21%, transient +17%, straight +57%) — flagged.
- V3 C_αr pegged at 500 kN/rad upper bound — flagged per skill.
- V3 still worse than V1 on cornering — flagged.
- No LOSO-CV variant attempted; any residual-learner result would be dishonest in-fold and was therefore not climbed.

Files: `tools/lateral_ladder.py`.
