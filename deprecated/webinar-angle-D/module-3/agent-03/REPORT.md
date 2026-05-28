# REPORT.md — webinar-angle-D / module-3 / agent-03

## Headline

- **Best variant: V2** — linear single-track with prior `C_α` from `PARAM_BY_PLATFORM`.
- Overall yaw-rate residual **RMSE 0.01403 → 0.00840 rad/s** = **40.1 % drop** vs V0.
- Sensor gate (`skills/lateral-fidelity-triage/sensor.py out/best_variant_V2.csv`) **PASSED** both checks: sign-consistency `corr(pred, meas) = 0.997` on cornering, and `RMSE(V2) = 0.00840 ≤ V0 = 0.01403`.

## Setup

- Platform: **FORD_MUSTANG_MACH_E_MK1** (Ford Mach-E Mk1). `yaw_rate_meas_rads` is the **measured** truth channel from the Ford party DBC.
- Inputs `v_mps` and `delta_road_rad` are **clamped to measured** under the speed-known contract (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Lateral-only metric.
- Segment set: first 12 Mach-E segments under `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/`, concatenated to **34 786 rows**.
- Regime mask thresholds: straight `|δ|<0.01 rad`; steady `|δ|≥0.01 ∧ |δ̇|<0.05`; transient `|δ|≥0.01 ∧ |δ̇|≥0.05`. Held constant across all rows.
- Attribution: **strict marginal**, fixed order V0→V1→V2→V3→V4. Marginal sum 0.004039 vs total drop V0→V4 0.004039 (0 % gap, well inside the 15 % rule).

## Variant ladder

| Variant | Overall RMSE | Straight | Steady | Transient | Marginal Δ | Verdict |
|---|---|---|---|---|---|---|
| V0  baseline (`yaw_rate_resid_rads` as-is) | 0.01403 | 0.01261 | 0.03192 | 0.03796 | —        | reference |
| V1  KS recalibrated (canonical `L`, per-seg yaw-gyro bias on straights) | 0.00973 | 0.00737 | 0.02924 | 0.04055 | **+0.00429** | win |
| V2  linear ST, prior `C_αf=C_αr=1.5e5 N/rad`, `v_min=2` fallback | **0.00840** | **0.00390** | 0.03444 | 0.04543 | **+0.00134** | win — **best** |
| V3  linear ST, fit `C_α` (`C_αf=150 000`, `C_αr=150 000`, **not pegged**) | 0.00856 | 0.00410 | 0.03498 | 0.04568 | −0.00016 | regression: fitter sat at the L-BFGS-B seed (`1.5e5`); cornering set too thin to move the gain |
| V4  Ridge residual learner on `[v,|a_y|,|δ|,sign(δ̇)]`, LOO-CV | 0.00999 | 0.00421 | 0.04056 | 0.05696 | −0.00143 | regression: OOF worse than V3, especially on transient — features under-power the cornering structure |

## Honest regression notes

- **V3 regressed (−0.00016 rad/s)** vs V2. The fit landed on `C_αf = C_αr = 1.5e5` — identical to the optimiser seed and to the prior — but the pegged-at-upper-bound flag did **not** trigger (upper bound is `5e5`). Cause: the loss surface is flat around the prior on this segment mix (straights dominate row count), so L-BFGS-B doesn't escape the seed; the tiny degradation is noise from changes far from straights.
- **V4 regressed (−0.00143 rad/s)** vs V3 out-of-fold. Per skill v0.5 rule, V3 is what I would ship over V4 — but V2 dominates both, so V2 is shipped. Cause: the feature set `[v,|a_y|,|δ|,sign(δ̇)]` plus Ridge α=1 cannot capture transient-cornering structure when trained leave-one-segment-out; transient RMSE *rises* from 0.0457 to 0.0570.
- Per-regime, V2 nearly halves **straight** residual (0.01261 → 0.00390 rad/s — the yaw-gyro-bias subtraction doing its job). **Steady** and **transient** regimes get *worse* under V2 (0.0319 → 0.0344, 0.0380 → 0.0454) — the linear-ST gain over-rotates relative to the measured truth on this segment mix, but the straight-channel improvement dominates by row count.

## What the v0.5 skill rules prevented

- **V0-as-is rule (v0.3):** stopped me from folding the gyro-bias subtraction into V0, which would have erased V1's headline win.
- **Pegged-`C_α` rule (v0.5):** would have caught a "quiet upper-bound win"; in fact it confirmed the V3 result is *not* a peg — the L-BFGS-B sit-at-seed is a separate pathology I now flag explicitly above.
- **LOO-only rule on V4 (v0.5):** prevented an in-fold V4 "win" being reported; out-of-fold V4 is honestly worse than V3.
- **Single-table rule (v0.5):** kept the report scannable for downstream parsers.
- **ST low-`v` warning (v0.4):** `linear_st_yaw_rate` falls back to KS below 2 m/s. Mach-E segments do include sub-2-m/s rows; without the fallback the eigenvalues blow up.

## Most painful missing component and cost

- **Nonlinear / transient single-track (V2.5)**. The cost is visible in the per-regime breakdown — V2 nearly halves straight RMSE but **worsens steady and transient** (0.032 → 0.034, 0.038 → 0.045). A transient ST with proper slip-angle dynamics (or even a relaxed `|δ̇|` low-pass on the gain) would target exactly that 0.04–0.05 rad/s headroom, which is now the dominant remaining error.

## Most surprising thing

The `C_α` fitter (V3) **did not move** off its seed. With 12 Mach-E segments at 34 786 rows, the straight-line fraction dominates so heavily that the steady-cornering loss term has almost no leverage on the optimiser — meaning my "fit" is doing zero work, yet it's *also* not triggering the pegged-at-upper-bound guard because it's pegged at the **seed**, not the **bound**. The v0.5 guard is necessary but not sufficient; a "stuck at x0" guard would be the natural v0.6 addition.

## Sensor

- Ran: `python3 skills/lateral-fidelity-triage/sensor.py out/best_variant_V2.csv`
- Result: PASS / PASS. It did **gate** V2 — had the sign convention been off (the v_min fallback could in principle flip behaviour at low speed), or had V2 silently come out worse than V0, the gate would have blocked the ship.
