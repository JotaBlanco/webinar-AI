---
name: baseline-residual
description: Compute the baseline lateral residual (RMSE ψ̇ in °/s, RMSE a_y in m/s², pred-vs-meas correlation) per Ford platform from existing sim CSVs. Load this skill whenever a task asks for "the current model's fidelity" or before any improvement is proposed.
when_to_use: First step of any lateral-fidelity work. Also as a sanity gate before reporting any "improvement" — you can only claim an improvement against a known baseline.
inputs: A directory of Ford sim CSVs (default `data/sim/segments/`).
outputs: One row per platform: `n_segments`, `RMSE_yaw_degs_mean`, `RMSE_a_y_mps2_mean`, `corr_yaw_mean`.
---

# Baseline residual — recipe

1. Confirm CSVs exist for both `FORD_MUSTANG_MACH_E_MK1` and `FORD_F_150_LIGHTNING_MK1` under `data/sim/segments/`. If missing or stale, regenerate with `python code/generate_simdata_ford.py` (output goes to `data/sim/` — for a per-module-isolated run, copy the script to your module's `out/` and redirect output).
2. Run `python skills/baseline-residual/compute.py [<sim-dir>]`. Default sim-dir = `data/sim/segments/`.
3. The script prints one row per platform. The number you report in REPORT.md as "baseline RMSE ψ̇" is the `RMSE_yaw_degs_mean` column.
4. Cross-check against `evals/baseline_rmse.py` — both should agree to rounding. If not, investigate before reporting.

## Gotchas

- Tesla CSVs have no `yaw_rate_meas_rads` — the script silently skips them. That is correct.
- The script reports the *mean across segments*, not a global RMSE. If you need a globally-pooled RMSE (concatenating samples), say so explicitly in the report.
- `corr_yaw_mean` < 0.9 with non-trivial RMSE means the model is wrong in *shape*, not just in scale. That changes which improvements make sense.
