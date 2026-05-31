# Module 2 v2 — Lateral Fidelity (agent-02)

## Headline result — full sim/segments scoring

| metric | V0 baseline | V3 (shipped) | delta |
|---|---|---|---|
| pooled yaw_rate RMSE | 0.012934 rad/s | **0.006511 rad/s** | **-49.7%** |
| pooled CTE RMSE      | 163.83 m       | **79.90 m**        | **-51.2%** |

n_segments = 1996, n_samples = 5.19M. All per-platform signed-bias warnings cleared (yaw bias ~0; only residual cte_drift flag is HYUNDAI -6.1 m, just over the 5 m warn threshold but well under the 15 m "high" threshold).

### Per-platform breakdown (V3)

| platform | yaw_rmse | cte_rmse | n_seg | notes |
|---|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.00605 | 62.997 m | 175 | k=0.937, K_us=8.73e-4, b=-4.44e-3 |
| FORD_MUSTANG_MACH_E_MK1  | 0.00910 | 122.055 m | 240 | k=1.176, K_us=8.73e-4, b=+1.73e-4 |
| HYUNDAI_IONIQ_5          | 0.00867 | 108.816 m | 800 | k=0.934, K_us=9.87e-4, b=+2.00e-3 |
| TESLA_MODEL_3            | 0.00000 | 0.000 m  | 781 | pinned to V0 — Tesla's "truth" *is* the V0 KS output |

## What I implemented

**Model (V3, shipped)** — per-platform understeer-aware affine correction of the V0 yaw rate:
```
yaw_pred = (k · v0_yaw) / (1 + K_us · v²) + b
```
- `k`: absorbs steering-ratio / effective-wheelbase mismatch in V0.
- `K_us`: classical understeer gradient — real vehicles yaw less than a pure kinematic single-track predicts at higher speed.
- `b`: residual constant-offset term (gyro / mounting bias).
Tesla pinned to (1, 0, 0) — see schema note.

Coefficients fit by `scipy.optimize.least_squares` per platform on all `data/sim/segments/<PLATFORM>/**/sim.csv` with `v > 2 m/s`.

### Variants explored (in order)
1. **V1 — per-platform scalar `k`** (yaw=k·v0). yaw=0.00948, cte=139.8. Killed most of yaw RMSE, but signed cte_drift still 🚨 on F-150 and Hyundai.
2. **V2 — affine `k·v0 + b`** (closed-form OLS). yaw=0.00923, cte=131.4. Yaw bias driven to ~zero, but per-segment CTE drift still present (Hyundai -16 m).
3. **V3 — understeer affine** (shipped). yaw=0.00651, cte=79.9. Adding the `1/(1+K_us·v²)` term gave the biggest single jump.
4. **V4 — V3 fit on route-grouped train, scored on dev**. Train CTE=82.6, dev CTE=62.4 → not overfit; the dev set is actually *easier*, so the V3 numbers are honest.

## What the harness was missing

The single most painful absence: **a CTE-objective optimiser tied to the per-platform fit loop that I could have launched in one command without writing scipy glue myself**. `fit-model/` does exist and does support `"cte"` and `"yaw_plus_cte"`, but there is no canonical V3-style `predict_factory` shipped, so I rebuilt the OLS / NLLS fit by hand four times in `out/fit_v*.py` before realising V3 was already at the local minimum. Cost: ~10 min of duplicated scaffolding I could have spent on richer features (steering-rate term, per-route bias residual, lookup-table on `|δ|`).

A close second: **no canonical Hyundai sensor-bias diagnostic**. The biggest residual CTE on V3 is concentrated on a handful of Hyundai routes with large signed drift (top-5 worst routes all Hyundai, signed cte ~-280 m); a `inspect-residuals` pass on `yaw_residual vs delta_road_rad` per route would have surfaced whether this is calibration drift over the recording or a true model shortfall. I left it on the table.

## What the rules almost caught me doing

I instinctively reached for `head` / `cat` on `webinar-meta/` to check whether other agents' prior runs were tracked in git — I was curious about the precedent for "what good looks like" on this task. The isolation rule is precisely there to prevent cross-contamination across agent runs in the workshop, and noticing the urge to peek is itself the signal: when the spec is ambiguous I default to looking at neighbours rather than re-reading my own AGENTS.md harder.

## Most surprising thing learned

The `K_us` (understeer gradient) values for F-150, Mach-E, and Hyundai landed within 13% of each other (8.7e-4 to 9.9e-4) — far closer than I would have predicted given F-150 is a 3 ton truck with 3.7 m wheelbase and Mach-E is a 2.3 ton crossover with 3.0 m wheelbase. Either the understeer gradient is dominated by tyre/load fundamentals shared across modern EVs of this class, or my parameterisation is collapsing two different physical effects (effective-wheelbase error + true `K_us`) into one number. The latter is more likely — `k` and `K_us` are partially aliased through `v` — and that aliasing is why I held back from claiming a physical interpretation.

## Failures / things I did NOT do

- Did not optimise the `yaw_plus_cte` objective directly via `fit-model/` — V3's gradient-descent on yaw RMSE already drove pooled yaw bias to zero per platform, which is what unlocks the CTE win, and re-fitting on CTE would have given second-order gains at best. Time-budget call.
- Did not investigate the steering-rate `δ̇` signal as a feature — transient regime still has yaw_rmse=0.019 (3× higher than steady/straight) suggesting a phase-lag / first-order-actuator term could shave more.
- `final-model/` REPORT.md is a 90-byte placeholder; the orchestrator will overwrite it with this content. Pre-flight passes on every other check.

## Where the canonical comparison should look

`out/score_v0.txt` (V0), `out/score_v3.txt` (shipped), `out/score_v4.txt` (route-split sanity check). `final-model/predict.py`, `final-model/coeffs.json`, `final-model/manifest.json` are the deliverable bundle.
