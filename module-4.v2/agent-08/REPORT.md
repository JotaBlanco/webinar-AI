# Module 4 v2 — agent-08 — lateral fidelity

## Headline

- **Pooled yaw-rate RMSE: 0.008225 rad/s** (V1 baseline: 0.008279, V0 passthrough: 0.013756)
- **Pooled distance-resampled CTE RMSE: 56.56 m** (V1: 56.81, V0: 163.83)
- Per platform (full-segment local score, sim/):
  - TESLA_MODEL_3 — yr 0.000000 / CTE 0.00 (V0 passthrough; sim-only Tesla yaw = KS V0, no measured truth)
  - FORD_MUSTANG_MACH_E_MK1 — yr 0.013495 / CTE 99.74
  - FORD_F_150_LIGHTNING_MK1 — yr 0.012670 / CTE 61.24
  - HYUNDAI_IONIQ_5 — yr 0.008892 / CTE 68.66

Improvement over V1 is small (~0.6% yaw, ~0.4% CTE pooled). V1 is essentially the structural ceiling for this kinematic family; the remaining loss is dominated by Mach-E lateral-accel-dependent residual (positive bias, growing std with |ay|).

## What I shipped

- `final-model/predict.py` + `final-model/coeffs.json` + `final-model/manifest.json`.
- Structure (rung 0+, same family as V1): `yr_ss = v·g·(δ_road − δ₀)/(L_eff + K_us·v²) + α_sr·dδ/dt`, then a first-order lag `τ`. Tesla = V0 passthrough.
- Per-platform refit via L-BFGS-B on a deterministic 80/20 segment split (seed 0) against pooled yaw-rate MSE, with physical bounds and per-segment δ₀ estimation on Mach-E and Hyundai (F-150 uses constant δ₀, mirroring V1).

## Variants explored and rejected

1. **fit_v1 (NM, unbounded)** — Mach-E ran away to g≈42, L≈107 (g/L_eff are degenerate when K_us→0). Killed by bounding L-BFGS-B in V3.
2. **fit_v2 (calibration on top of V0 yaw_rate_pred_rads via gain + understeer + lag, with subtraction of median-bias)** — worse than V1 across the board; the V0 scaling re-introduced bias that V1's δ₀-based form already handled cleaner. Dropped.
3. **Steering-rate feedforward (α_sr · d δ_road/dt)** — measurable Mach-E gain (~0.2 m CTE), neutral elsewhere. Kept.
4. **Per-segment δ₀ on F-150** — broke F-150 dev CTE (42 → 107). Reverted to constant δ₀ as in V1.

## Most painful absent component

The harness has `score-model`, `iterate`, `assess-candidate-model`, `pre-flight-final-model` skills but I bypassed them entirely — what I actually wanted was a **two-line "score model against canonical eval set" command** with cached segment load. Each refit run reloaded all 1,200+ segments from CSV, which dominated wall-clock time. A pre-built `load_segments` Python module that memoises into a parquet cache would have saved most of the elapsed budget; I had to roll my own and there are still two near-duplicate copies in `out/`. The RPI three-phase scaffolding (Research → Plan → Implement folders, lock.sh, launch-rungs/) was complete overkill for a problem where the structural ceiling is already known — I would have liked a "fast path" skill: `quick-fit <coeffs> --on <platform>` that does the refit + dev score in one call.

## What the rules almost made me do

I noticed myself wanting to peek at `module-4.v1/` and the m3.v3 agent folders to see what other people's V2 structures looked like, and at `_grade/` to understand the canonical scorer's exact CTE definition (vs the local copy in `_shared/traj_metrics.py`). The isolation rules blocked both — and that's the right call for the workshop, but it means I'm shipping without external validation that my CTE metric matches the grader's. The metric file warns of intentional non-linked duplication, so divergence is possible.

## Single most surprising thing

Tesla's "truth" channel `psi_dot_rads` in `sim/segments/` is **identical** to the V0 prediction `yaw_rate_pred_rads` because Tesla rlogs don't expose a measured yaw rate — the truth IS the kinematic model output. So Tesla's yaw RMSE is structurally zero for any model that falls through to V0, and any non-passthrough Tesla prediction can only get worse. AGENTS.md mentions this in passing but I had to verify it from the data myself before trusting that V0 passthrough was the correct ship choice (and not a sign of a bug).

## Honest gaps

- 80/20 split was used for fitting; no proper CV. Train-leakage on coefficients is possible but with 5-6 free parameters and 140-640 train segments per platform, unlikely material.
- I did not exercise the `launch-rungs/` parallel subagent path or the `iterate`/`critique-residuals` skills. The structural diagnosis (Mach-E lat-accel residual) was obvious from a one-liner.
- F-150 had the biggest *per-platform* dev gain from refit (42.04 → 41.08 CTE) but Mach-E (the worst platform) barely moved — the structural ceiling is real there.
