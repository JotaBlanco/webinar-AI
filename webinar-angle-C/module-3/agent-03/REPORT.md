# Module-3 / agent-03 (angle-C) — Lateral fidelity

**Headline.** Per-platform yaw-rate gain correction (V2) is the only variant that moves the needle. On Mustang Mach-E it cuts transient RMSE by 12.7% and steady by 6.2% but **regresses straight RMSE by +19%** (intercept leaks onto straights). On F-150 Lightning it improves every regime, dropping overall by 19.3%. V1 (static bias) is null on Mustang and small on F-150. V3 (understeer gradient) is rejected by the data — fitted K ≈ 0 on both platforms.

**Platform & truth.** Ford only: `FORD_MUSTANG_MACH_E_MK1` (315 seg / 913 626 samples) and `FORD_F_150_LIGHTNING_MK1` (230 seg / 667 141 samples). Truth channels `yaw_rate_meas_rads`, `a_lat_meas_mps2` decoded from rlog. Tesla excluded (rule 4).

**Clamped vs predicted.** `v` and `δ` are clamped to measured (lateral-only mode). Only ψ̇, a_y, x, y, ψ are predicted. Speed-state error is zero by construction (rule 5).

**Train/test.** Interleaved every-5th-sample, test = idx % 5 == 0 (rule 7). All RMSEs are TEST.

## Variant ladder — accounting: cumulative (Δ from previous rung, overall RMSE rad/s)

| Rung | Mustang overall | straight | steady | transient | F-150 overall | straight | steady | transient |
|---|---|---|---|---|---|---|---|---|
| V0 baseline | 0.01613 | 0.00878 | 0.03147 | 0.05743 | 0.02037 | 0.00899 | 0.03629 | 0.05161 |
| V1 +bias (per-platform) | 0.01616 | 0.00875 | 0.03159 | 0.05754 | 0.02007 | 0.00800 | 0.03636 | 0.05162 |
| V2 +gain (per-platform) | 0.01597 | 0.01043 | 0.02952 | 0.05013 | 0.01643 | 0.00664 | 0.02865 | 0.04472 |
| V3 +understeer-K (per-platform) | 0.01597 | 0.01044 | 0.02950 | 0.05014 | 0.01643 | 0.00664 | 0.02867 | 0.04472 |

Fits: Mustang `bias=+0.00110, a=+0.00396, b=1.0942, K=-9.6e-5`. F-150 `bias=+0.00461, a=+0.00168, b=0.8674, K=+5.6e-5`. All fits **per-platform**, not per-segment (rule 8). a_y_pred re-derived as `v·ψ̇_pred` at every rung (rule 9).

## Painful absence

Static yaw bias on Mustang is below the noise floor (1.1 mrad/s vs straight residual 8.8 mrad/s). The team's intuition that there is a sensor offset to subtract is not supported by Mustang data; on F-150 there is a small one (4.6 mrad/s).

## Near-misses

V2 helps on Mustang but the intercept `a=+0.004` leaks onto straights and inflates straight RMSE by 19% — physical cause: a single linear correction can't separate cornering gain from straight-line offset. A future V2′ would fit zero-intercept on cornering and re-bias on straights.

## Surprise

The kinematic-vs-truth gain `b` flips sign across platforms: Mustang `b=1.094` (KS under-predicts ψ̇) vs F-150 `b=0.867` (KS over-predicts). No single global multiplier works. Most likely root cause is per-platform effective steer-ratio / rack compliance — worth a follow-up that adjusts `i_s` in `code/parameters.py::PARAM_BY_PLATFORM` rather than band-aiding the prediction post-hoc.

## Regressions flagged (with physical cause)

Mustang straight RMSE +19% at V2: intercept `a` from cornering regression is non-zero on straights where the underlying residual is sensor-noise floor. Causal, not statistical — pure leakage from the variant's degree of freedom.

## RPI artifacts

- Research: `rpi/runs/20260527-160000/research.md`
- Plan (locked): `rpi/runs/20260527-160000/plan.md`
- Implement notes: `rpi/runs/20260527-160000/implement-notes.md`

## Evals

`evals/schema_check.py` PASS on `out/FORD_MUSTANG_MACH_E_MK1/sim_v3.csv` and `out/FORD_F_150_LIGHTNING_MK1/sim_v3.csv`. `evals/baseline_rmse.py` numbers match the V0 row above (overall 0.01613 / 0.02037 — rule 11 confirmed: same segment set + regime mask used at every rung).
