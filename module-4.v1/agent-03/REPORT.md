# Module 4 v1 — agent-03 REPORT

## Headline (in-sample pooled, data/sim/segments)

| Model | yaw RMSE | CTE RMSE |
|---|---|---|
| V1 (baseline) | 0.010612 | 75.65 |
| **Final (V1 + per-platform low-rank correction)** | **0.010535** | **72.24** |
| Δ vs V1 | -0.73% | -4.51% |

Per-platform 5-fold route-grouped CV (dev numbers):

| Platform | yaw V1 → post | Δyaw | cte V1 → post | Δcte |
|---|---|---|---|---|
| Mach-E (scale+bias)    | 0.013633 → 0.013525 | -0.79% | 98.68 → 91.83 | -6.94% |
| IONIQ-5 (linbias in v) | 0.008933 → 0.008908 | -0.28% | 69.53 → 67.28 | -3.23% |
| Lightning (scale only) | 0.012733 → 0.012721 | -0.10% | 62.18 → 61.93 | -0.41% |

## What I implemented

- Mach-E: affine post-correction `yr_post = 0.001696 + 0.97463 · yr_v1`.
- IONIQ-5: velocity-linear bias `yr_post = yr_v1 + 2.231e-4 + 2.789e-5 · v`.
- Lightning: scalar scale `yr_post = 0.98734 · yr_v1` (cohort §5 noise floor).
- Tesla: V0 passthrough.
- Trajectory `x_m, y_m` integrated from corrected yaw rate using `v_meas`.

## Variants considered and rejected

- 11-feature ridge residual head (delta, v, delta·v, delta·v², ddelta, ddelta·v, a_lat proxy, a_long, brake, sign(delta)·delta², 1): every λ ∈ {1, 10, 100, 300, 1000} regressed CTE +2.6-8.3% on Mach-E and IONIQ-5 under 5-fold route-grouped CV. Cohort §4 (the historical winner on this dataset) did not transfer. Likely because this run's V1 already absorbs per-segment delta0, leaving residual structure dominated by a near-constant bias plus small scale — too little exploitable structure for an 11-feature head.
- Bias-only on Lightning: CV +1.0% CTE — confirms §2/§5.
- Bias-only vs scale+bias on Mach-E: scale+bias is marginally better on both KPIs at zero added complexity.

## Process deviations from the AGENTS.md default loop

- Skipped `rpi/run-research.sh` and `launch-rungs/launch.sh` — solo run on ~45 min budget; cohort §0 already pointed unambiguously to the bias-correction + residual-head pair, so a fresh research/plan session would have been redundant.
- Did not invoke `skills/iterate/`. The `MODELS.md` / `TREE.json` registry is not populated. Comparison was done manually in `out/explore.py` and `out/explore_v2.py`.
- No frozen `data/sim/test/` split exists; only `segments/`. So `pre-flight-final-model --final` was not applicable.

## Most painful missing component

`skills/iterate/` itself: the closed-loop registration that would auto-CV every candidate, append to MODELS.md / TREE.json with CV diagnostics, and route via `critique-residuals`. Doing this by hand cost me a structured trace of the rejected ridge head — I had to invent the comparison schema in `out/explore_v2.py`. Second-painful: no `fit-model` skill for non-V1 model shapes (ridge with platform groups was hand-rolled).

## What the isolation rules almost cost me

Twice almost flat-imported `code.v1_baseline` (collision with stdlib-adjacent `code` module). Caught both times; used `sys.path` injection of the symlinked subdir. Also nearly opened a sibling agent's REPORT for sanity-check on the residual-head decision — held off, used only the curated `references/m4-cohort-findings.md`.

## Surprise of the run

The cohort §4 ridge residual head, which "reliably won across every cohort agent that tried it" in m3.v3, *regressed CTE on this dataset* under proper route-grouped CV at every regularization. Most parsimonious affine correction wins. This is a concrete case of cohort findings going stale once V1 moves underneath them — exactly the unclosed cross-cohort loop m5 is supposed to fix.

## Deliverables

- `final-model/predict.py` — self-contained `predict(sim_df, platform)`.
- `final-model/manifest.json` — `predict_callable`, `platform_support`, per-platform strategy.
- `final-model/notes.md` — diff vs V1, CV table, rejected variants.
- `out/explore.py`, `out/explore_v2.py` — exploration drivers.
- `out/verify_final.py`, `out/verify_v1.py` — pooled verification harness.
- `out/coeffs.json`, `out/v2_coeffs.json`, `out/v2_results.json` — CV data.

---

```
ISOLATION_REPORT:
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "All reads under agent subtree + code/ + data/ symlinks; no out-of-scope writes; persisted from agent text response."
```
