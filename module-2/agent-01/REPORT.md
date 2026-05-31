# Module-2 agent-01 — Lateral-fidelity report

## Headline numerical result (pooled across all scored segments, `data/sim/segments/`)

| Metric                      | V0 baseline | V1 (shipped) | Reduction |
|-----------------------------|-------------|--------------|-----------|
| Yaw-rate RMSE (rad/s)       | 0.016773    | **0.008623** | -48.6%    |
| Distance-resampled CTE RMSE | 218.16 m    | **104.62 m** | -52.0%    |
| Segments scored / failed    | 1215 / 781  | 1215 / 781   | —         |

Per-platform yaw RMSE (V1): F-150 0.00632, Mach-E 0.00953, Ioniq-5 0.00876.
Per-regime yaw RMSE (V1): straight 0.00678, steady 0.01066, transient 0.02412 (transient is where the kinematic model still loses).
Per-platform CTE RMSE (V1): F-150 64.3 m, Mach-E 122.1 m, Ioniq-5 105.9 m.

Failed-segment count (781) is dominated by TESLA_MODEL_3 (no truth in local sim/) plus a small number of too-short segments — these are skipped by `score-model`, not by `predict`, which handles all four platforms in `data/sim-only/segments/`.

## What I implemented

Single variant, per-platform fit:
- **V1 — bicycle-with-understeer + affine**: `yr = gain * (v * delta_road / (L + K * v^2)) + bias`, with `(L, K, gain, bias)` fit per platform via grid-search over `K∈[0,…]` then closed-form affine on residuals (`out/fit_coeffs.py`). Adds one linearised tire-slip term to V0's kinematic single-track and absorbs steady-state miscalibration (steer-ratio, sensor zero, suspension compliance) with affine `gain`/`bias`.
- **TESLA fallback** — passthrough of V0's `yaw_rate_pred_rads` (no truth available locally, so no way to fit). Documented in `coeffs.json` and `manifest.json`.

Trajectory `x_m, y_m` are intentionally omitted; the grader integrates from `yaw_rate_pred_rads + v_mps` per the operating contract, which is exactly what `score-model` does locally — so what was tuned is what gets graded.

Pre-flight check status: predict imports, has correct signature, returns aligned DataFrame with `yaw_rate_pred_rads` (no NaN) on all four platforms against actual `data/sim-only/segments/` inputs. The `report_md_present` and `predict_returns_correct_shape` preflight checks failed only because (a) REPORT.md is being returned via this message per harness friction and (b) the skill globs `data/sim-only/<PLAT>/**/sim.csv` but actual layout is `data/sim-only/segments/<PLAT>/...` — I verified by hand against the real layout and got clean returns on all four platforms.

## Most painful absence in the harness

**No tire-slip / lateral-dynamics model template in `_shared/`.** I had `traj_metrics.py` (integration + CTE) and `ks_model.py` (kinematic baseline), but no scaffolding for a linear bicycle model with tire stiffness — even a stub that exposed `Cf, Cr, m, Iz` per platform would have collapsed the "guess functional form + grid-search K" loop into a closed-form fit. Cost: most of the iteration time went into deciding how aggressive to make the dynamic correction (understeer-only) vs. risking overfit; with a proper dynamic-model module I would have tried a real linear bicycle and probably squeezed transient RMSE (currently 0.0241) down further.

Secondary absence: no per-platform vehicle-parameter sheet (wheelbase, mass, CG, tire data) — I used reasonable book values for `L` and let the fit absorb the rest.

## What I almost did that the rules prevented

I almost reached into `module-1/agent-XX/final-model/` to crib coefficient values or fit strategies from a prior solve — the isolation rules stopped me cold. I also wanted to peek at `_grade/` to confirm exactly which segments are used at grading (and which v-filter threshold), but accepted the local `score-model` definition as the contract.

## Single most surprising thing I learned

The Mustang Mach-E needed a **`gain` of 1.21** — twenty per cent above unity — to match truth, while the F-150 (0.977) and Ioniq-5 (0.943) sit below. That asymmetry says the published wheelbase or steer-ratio for the Mach-E in the upstream KS model is meaningfully wrong, not just slightly off; the fitted gain is doing structural work, not just trimming a bias. A real linear bicycle fit per platform would probably split that gain into "steer-ratio error" vs. "understeer", which would be informative for the upstream model maintainers.

## Harness friction encountered
- Sub-agent write-block on `*report*.md` etc. — handled by returning content above for the orchestrator to persist.
- `score-model._default_segment_paths` looks under `data/sim-full/FORD_*/…` but the actual layout is `data/sim/segments/<PLATFORM>/…`. Had to pass explicit `segment_paths`.
- `pre-flight-final-model._smoke` looks under `data/sim-only/FORD_MUSTANG_MACH_E_MK1/…` directly but layout has a `segments/` subdir. The check skips rather than fails on missing sample — I validated by hand.

## Files shipped
- `final-model/predict.py`
- `final-model/manifest.json`
- `final-model/coeffs.json`
- `out/fit_coeffs.py` (fit script)
- `out/score_v0.py`, `out/score_final.py`
- `out/score_summary.json`

ISOLATION_REPORT:
```
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "Wrote only inside module-2/agent-01/ (out/ and existing final-model/). Did not modify code/ or data/. The score-model and preflight skills have hard-coded paths (data/sim-full/, data/sim-only/<PLAT>/) that don't match this module's data layout (data/sim/segments/, data/sim-only/segments/<PLAT>/); worked around by passing explicit segment_paths and validating predict by hand."
```
