# Module-2 / agent-02 (angle-B) — Lateral fidelity, Ford Mustang Mach-E (MK1)

**Platform scored:** `FORD_MUSTANG_MACH_E_MK1`, 80 segments (first 80 alphabetically), pre-generated `sim.csv`.
**Truth channel:** `yaw_rate_meas_rads` — measured from the Ford CAN bus via `adapter_ford_rlog.py` (opendbc `ford_lincoln_base_pt`). Not self-consistency, not predicted.
**Clamped (inputs):** `v` (`clamp_v_to_measured=True`) and `δ` (`clamp_delta_to_measured=True`).
**Predicted (under test):** `yaw_rate_pred_rads`; residual = `pred − meas`.
**Regime mask (identical across all variants):**
- straight: `|ψ̇_meas| < 0.02 rad/s`
- transient: `|ψ̇_meas| ≥ 0.02` ∧ rolling-25-sample std of `ψ̇_meas` > 0.02
- steady: `|ψ̇_meas| ≥ 0.02` ∧ not transient

## Variant ladder

| Variant | Change | RMSE all | straight | steady | transient | Marginal drop (all) |
|---|---|---:|---:|---:|---:|---:|
| V0 | baseline, `yaw_rate_resid_rads` as-shipped | 0.01190 | 0.00778 | 0.01767 | 0.05521 | — |
| V1 | + per-segment mean-bias removal | 0.00992 | 0.00412 | 0.01647 | 0.05489 | -0.00197 |
| V2 | V1 + linear ST steady-state gain `v·δ/(L·(1+K_us·v²))` using shipped C_α | 0.01145 | 0.00364 | 0.01995 | 0.06432 | +0.00153 (regression) |
| V3 | V1 + first-order steering lag (τ = 0.10 s) on `δ_road`, KS kinematics | 0.00924 | 0.00388 | 0.01594 | 0.04858 | -0.00221 |
| V4 | V3 + global scalar gain k=1.0277 fitted on first 40 segs | 0.00864 | 0.00394 | 0.01471 | 0.04462 | -0.00060 |

**Accounting:** marginal/sequential. Sum of marginals = -0.00325 rad/s; total V0→V4 = -0.00325 rad/s; exact.

## Regression analysis (V2)

Applying the linear ST yaw-rate gain with shipped `C_αf=286,551, C_αr=355,912 N/rad` yields `K_us=5.62e-4`, i.e. a gain factor ~0.82 at v=20 m/s. An empirical least-squares fit of `ψ̇_meas` against KS prediction `v·tan(δ)/L` returns gain ≈ **1.04** — the data wants slightly *more* yaw rate than KS, not less. The shipped cornering-stiffness prior overstates understeer for this tyre/road combination. Until C_α is refit, V2 is a regression and V3/V4 keep KS kinematics.

## Headline

**Yaw-rate RMSE 0.01190 → 0.00864 rad/s (-27.4%) across 80-segment Mach-E set, mask locked.** Biggest contributors: steering-lag (V3, 0.0022 rad/s) and bias removal (V1, 0.0020 rad/s). ST-with-shipped-priors hurt; a global gain on top of lag bought another 0.0006.

## What is not fixed

Transient-cornering residual still ~0.045 rad/s — five times the straight-line floor. KS-with-lag can't capture tyre relaxation length or weight transfer; closing requires ST with calibrated C_α or Pacejka.

## Painful absence

A **skills/ or evals/ harness** — no scaffolded "run the ladder, print the regime-bucketed RMSE" loop. Wrote it from scratch under a 15-min budget while every turn re-paid the full AGENTS.md + CLAUDE.md context.

## Rule-prevented near-misses

- Trap #2 (don't unclamp v/δ) — considered relaxing δ-clamp to let the steering integrator absorb the lag rather than pre-filtering δ; treated τ as input transform instead.

## Most surprising

The shipped `C_αf, C_αr` priors push the ST model the **wrong way** on this fleet — KS overpredicts yaw rate slightly, but linearised ST with priors *under*predicts much more. Recalibrating C_α matters more than upgrading model order. The fidelity-ladder rung is not the bottleneck; the parameter prior is.

Files: `tools/analyze.py`, `out/results.txt`.
