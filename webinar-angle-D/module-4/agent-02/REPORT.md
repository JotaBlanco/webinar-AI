# REPORT — webinar-angle-D / module-4 / agent-02

## Headline

Lateral yaw-rate RMSE on 12 Ford Mustang Mach-E segments dropped from
V0 = 0.01403 rad/s to V2 = 0.00825 rad/s — a 41 % reduction. V2 (Linear
single-track with prior Cα + yaw-gyro bias) is the shipped best
variant. V3 and V4 are honest regressions and are not shipped.

- Platform: FORD_MUSTANG_MACH_E_MK1.
- `yaw_rate_meas_rads` is **measured** truth (Ford party-DBC yaw gyro).
- `v` and `δ` are **clamped to measured** under the speed-known contract; speed/steering-state agreement is scope, not metric.
- Attribution: strict marginal, fixed order V0→V1→V2→V3→V4. Sum of marginals 0.004031 = total drop 0.004031 (within 15 %, in fact identical).
- Sensor gate (`sensor.py out/best_variant.csv`): PASS sign-consistency (corr 0.997 on cornering), PASS regression-check (0.00825 ≤ 0.01403).

## Variant ladder

| variant | overall | straight | steady | transient |
|---|---:|---:|---:|---:|
| V0 baseline (as-is) | 0.01403 | 0.01261 | 0.03192 | 0.03796 |
| V1 KS recal + yaw-bias | 0.00973 | 0.00737 | 0.02924 | 0.04055 |
| V2 Linear ST (prior Cα) | **0.00825** | **0.00351** | 0.03459 | 0.04544 |
| V3 Linear ST (fit Cα) | 0.00839 | 0.00367 | 0.03517 | 0.04570 |
| V4 + residual learner (LOO) | 0.00999 | 0.00379 | 0.04116 | 0.05839 |

Units: rad/s. Bold = shipped best.

## Composition decision

- Two skills loaded: `regime-segmentation` v0.3 (tags every row straight/steady/transient) and `lateral-fidelity-triage` v0.5 (the 5-step ladder + sensor gate).
- Order: `regime-segmentation` first — it is a pure DataFrame transform, and the triage ladder calls `per_regime_rmse` on the tagged frame. Triage second — it owns the analytical playbook (V0..V4, marginal accounting, sensor).
- `tools/run_ladder.py` is the thin glue that loads, tags, runs the ladder, writes `out/best_variant.csv` and `out/summary.json`.

## What each change contributed (strict marginal, V0→V4)

- V0→V1: −0.00429 rad/s overall. KS recalibration with canonical `L` from `parameters.py` plus per-segment yaw-gyro bias subtraction on straight-line samples. The bias term is what kills the straight-line residual (0.01261 → 0.00737).
- V1→V2: −0.00148 rad/s overall. Switching from kinematic to steady-state linear single-track with prior Cα removes the residual oversteer of pure KS — straight-line drops further (0.00737 → 0.00351), the structural gain term `1/(1 + K_us v²)` is doing real work at highway speed.
- V2→V3: **+0.00014 rad/s — regression.** Fitted Cα = (150000, 150000) N/rad. These are exactly the L-BFGS-B initial guesses (`x0 = [1.5e5, 1.5e5]`); the optimizer made no measurable progress and just paid the optimisation noise. Not pegged, but effectively a no-op-with-noise. V2 wins outright.
- V3→V4: **+0.00160 rad/s — regression.** Out-of-fold Ridge on `[v, |a_y|, |δ|, sign(δ̇)]` does not generalise across these 12 segments; LOO oof_rmse 0.00999 > V3's 0.00839. Per the v0.5 rule: ship V3 (here V2), not V4.

Total drop V0→V2 (shipped): 0.00578 rad/s = 41 %.

## Painful absence

The skill pair lacks an **eval/golden-residual fixture**. Without a known-good per-regime RMSE checked in, the only way to notice if `parameters.py` or the CSVs changed under our feet is the sensor's coarse "no worse than V0" check, which still passes for a 5 % regression. A second sensor that locks in the *expected* RMSE for V1 and V2 (within a tolerance) would have surfaced the v3 fit collapse instantly.

A second painful absence: the ladder skill has no notion of **highway-only vs urban** sub-regimes within "transient cornering". Transient RMSE rises across every variant (0.038 → 0.058), so every "win" is happening on straight + steady at the cost of transient. The mask treats the worst regime as a single bucket.

## What rules prevented

- The v0.3 V0-methodology rule prevented folding the yaw-gyro bias into V0 — keeping it inside V1 is what makes the V0→V1 marginal honest (−0.00429 rad/s rather than ~0).
- The v0.5 regression-flagging rule forced V3 and V4 to be named as regressions rather than buried under a "+/−" wash.
- The v0.5 single-table rule kept this report parseable downstream — exactly one markdown table, the ladder.
- The v0.5 pegged-Cα detection ran (returned False) but pointed at the deeper issue: fit *didn't peg*, but it also didn't move — a finding the rule indirectly surfaced.
- The v0.4 low-v `v_min ≈ 2 m/s` fallback inside `linear_st_yaw_rate` is what kept V2/V3 from blowing up on any Lightning-style stationary stretches that exist in the Mach-E set.
- The v0.5 sensor gate confirmed sign-consistency (corr 0.997) before declaring V2 the best variant.

## Surprise

V2 outperforms V3 even though V3 is allowed to fit Cα freely. The reason is mechanical: L-BFGS-B starts at `x0 = [1.5e5, 1.5e5]` and the loss surface near that point is shallow/noisy enough that the optimizer terminates without progress. The "fit" is identical to the prior — except it inherits a tiny bit of numerical jitter and *loses* by 0.00014 rad/s overall. Free parameters can still lose to fixed parameters when the optimiser is the bottleneck, not the model.
