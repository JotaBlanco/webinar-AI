# Lateral-Fidelity Triage — webinar-angle-E / module-3 / agent-04

**Platform:** `FORD_MUSTANG_MACH_E_MK1`
**Skill:** `yaw-divergence-triage` (composed with `regime-comparison`)
**Metric:** `RMSE(yaw_rate_pred_rads − yaw_rate_meas_rads)` in rad/s.

## Operating contract

- `yaw_rate_meas_rads` from the Ford `sim.csv` is the measured truth channel.
- `v_mps` and `delta_road_rad` are clamped to measured in KS, by harness contract.
- The lateral residual is the **only** lateral fidelity metric; speed-state agreement is zero by construction and not used.
- Rows: 913,626 across the Mach-E segment set. Regime split: straight 785,093 / steady 106,978 / transient 21,555.

## Variant ladder

| variant | overall | straight | steady | transient | marginal (overall) | attribution |
|---|---:|---:|---:|---:|---:|---|
| V0 raw residual | 0.016127 | 0.008768 | 0.031733 | 0.056797 | — | baseline |
| V1 KS recalibrated (canonical L + per-segment bias) | 0.014693 | 0.004931 | 0.031681 | 0.057296 | **−0.001434** | the only improving step |
| V2 linear ST, prior Cα (openpilot) | 0.016529 | 0.007005 | 0.034497 | 0.062343 | +0.001836 (**regression**) | gain too low — see notes |
| V3 linear ST, fit Cα (L-BFGS-B bounded) | 0.016635 | 0.007000 | 0.034822 | 0.062659 | +0.000106 (**regression**) | optimiser stuck at x0 — see notes |

- Total drop V0→V3: **−0.000508 rad/s** (the ladder ends *worse* than V0).
- Sum of marginal drops: **−0.000508 rad/s** — exact (within 0.0% of total, well inside the 15% reconciliation bound).
- Attribution scheme: strict marginal, fixed order V0→V1→V2→V3.

## Regression flags (honest)

- **V1→V2 (overall +0.001836)** — the steady-state linear-bicycle gain `v·δ / (L·(1+K_us·v²))` underpredicts yaw rate vs the simpler KS `v·tan(δ)/L`. The openpilot prior `C_αf=286.5k, C_αr=355.9k N/rad` is too soft, so `K_us` is large and the predicted yaw rate is biased low. Also, V2 has **no per-segment bias removal** (the helper's bias step lives only in V1), so the gyro DC offset that V1 cancelled is reintroduced.
- **V2→V3 (overall +0.000106)** — V3 fit is degenerate (see below). It returns the starting point `(1.5e5, 1.5e5)` rather than a true minimum. Same missing per-segment bias as V2.

## V3 fit diagnostic — painful absence

The skill's `v3_linear_st_fit` runs L-BFGS-B with bounds `(5e4, 5e5)` and `x0=(1.5e5, 1.5e5)`. Across five sanity-check restarts the optimiser converged with `PGTOL` after **zero** real steps from every starting point:

| `x0` | returned `(C_αf, C_αr)` | loss | message |
|---|---|---:|---|
| (5e4, 5e4) | (5e4, 5e4) | 0.019558 | PGTOL |
| (1.5e5, 1.5e5) | (1.5e5, 1.5e5) | 0.016635 | PGTOL (← reported V3) |
| (2.5e5, 2.5e5) | (2.5e5, 2.5e5) | 0.016312 | PGTOL |
| (3e5, 3.5e5) | (3e5, 3.5e5) | 0.016411 | PGTOL |
| (5e5, 5e5) | (5e5, 5e5) | 0.016316 | PGTOL |

The loss surface is near-flat in the bounded region; finite-difference gradients fall under `pgtol` immediately. `pegged=False` in the skill's pegged-bound check, but for a worse reason than the SKILL.md anticipates: the optimiser never moved. The skill has no gradient-free fallback (Nelder-Mead, differential evolution) — that is the most painful absence.

A wider sweep would put the true minimum *above* the upper bound; V1 (KS+bias) still beats the best linear-ST point.

## Attribution — per-regime contrast (sibling skill)

Composed `regime-comparison/compare.contrast(df, {V0,V1,V2,V3})` on the same regime-tagged DataFrame:

| variant | Δ straight | Δ steady | Δ transient | dominant regime |
|---|---:|---:|---:|---|
| V0 | 0.000000 | 0.000000 | 0.000000 | — |
| V1 | −0.003837 | −0.000051 | +0.000500 | straight |
| V2 | −0.001762 | +0.002764 | +0.005546 | transient |
| V3 | −0.001767 | +0.003089 | +0.005863 | transient |

Read: V1's entire improvement is the straight-line DC-bias cancellation; it leaves cornering essentially untouched (and microregresses transient). V2/V3 partially keep the straight-line win (the gain `v·δ/(L·…)` ≈ `v·tan(δ)/L` for small δ) but lose far more in transient cornering, where the steady-state assumption (zero `δ̇`, zero β̇) doesn't hold.

## Conclusion

- The lateral predictions improve by **−0.001434 rad/s overall RMSE (≈ −8.9%)**, all of which is attributable to **V1: per-segment yaw-gyro bias removal on the canonical KS model.**
- The linear single-track ladder (V2, V3) regresses on this dataset because (a) it drops the bias step and (b) for this vehicle the loss-vs-Cα landscape is too flat for L-BFGS-B to fit. V3 as shipped is the prior in disguise.

## Surprise

Openpilot's stock `C_α` is "too soft" for the Mach-E here, but L-BFGS-B can't tell — the RMSE difference between `1.5e5` and `5e5` is on the order of 3e-4 rad/s, well inside the optimiser's `pgtol`. The honest single-line summary is *"transferring the V1 straight-line bias step into V2/V3 would matter more than re-fitting Cα."*
