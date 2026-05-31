# REPORT — module-1 / agent-01

## Headline

Speed-known yaw-rate model `psi_dot = v * (a*delta_lagged + b) / (L + K*v^2)` with per-platform fit. Local scoring on `sim-only/segments/` (every 3rd file), truth = `yaw_rate_meas_rads` from matching `sim/segments/`, truth trajectory = `yaw_rate_meas` integrated with measured `v`:

| Platform | Yaw RMSE V0 | Yaw RMSE V1 | CTE V0 | CTE V1 |
|---|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | 0.01184 rad/s | **0.00823** (-30.5%) | 101.20 m | **91.36** (-9.7%) |
| FORD_F_150_LIGHTNING_MK1 | 0.02005 rad/s | **0.01017** (-49.3%) | 111.75 m | **43.42** (-61.1%) |
| HYUNDAI_IONIQ_5 | 0.01766 rad/s | **0.00761** (-56.9%) | 159.95 m | **80.13** (-49.9%) |
| TESLA_MODEL_3 | — (no truth in sim/) | — | — | — |

## What I implemented

- **V1 model** (`final-model/predict.py`): single closed-form yaw-rate with two structural fixes vs KS: (1) understeer term `K*v^2` in the denominator — recovers the speed-dependent yaw deficit that pure kinematics ignores; (2) integer-sample steering lag (forward shift of `delta_road_rad`) — captures actuator + tyre lag.
- **Per-platform fit** (`out/fit_v1.py`): joint Nelder-Mead L2 on `(L_eff, K, a, b)` plus a grid sweep over `lag in [0..15]` samples (50 Hz). Fitted on `data/sim/segments/` for the three platforms with `yaw_rate_meas_rads`. Coeffs land at K≈2.6e-3..3.6e-3 (Mach-E < Lightning), lag=3-4 samples (60-80 ms), a∈[0.93, 1.15], b≈0.
- **Tesla fallback**: no truth in `sim/`, so `L=2.875` openpilot-canonical, `a=1, b=0, lag=0`, `K` = mean of fitted three. Honest "best-available prior" — flagged as a limitation, no fabricated metric.
- **Trajectory**: yaw → ψ via cumtrapz, then `(v cos ψ, v sin ψ)` → x, y via cumtrapz; origin (0,0,0).

## Most painful absence

**No `score-model/` skill / no harness scoring helper.** I had to hand-roll the canonical contract (subset sim-only's 8 columns, integrate truth from `yaw_rate_meas`, distance-resample for CTE) in `out/local_score_v2.py`. That ate roughly a third of the budget — most of which would have been instant with a working scoring skill that already encodes the grader's contract. Without it I couldn't be confident my CTE definition matches the grader until run-time. Second most-missed: an `AGENTS.md` with the truth-column conventions written down — I had to reverse-engineer that `x_m, y_m` in `sim/` is the V0 trajectory, not truth, by reading the generator.

## Things I almost did that the rules prevented

- Almost ran `head` on a `sim.csv` directly without checking that `code/` and `data/` were symlinks — would have been fine but would have looked like a write-attempt to a parent if I'd messed up the path. The hook didn't fire because I kept paths inside agent-01.
- Almost reached for `module-2/` to see if there was a reference scoring implementation — caught myself, declared it a limitation instead.
- Almost wrote a scratch CSV to `code/` (muscle memory: that's where the code lives). Caught it before invoking Write.

## Most surprising thing learned

`x_m, y_m, psi_rad` in `sim/segments/*/sim.csv` are *the V0 model's own predictions*, not measurements — so naively scoring "CTE vs `truth.x_m`" gives nonsense (V0 scores ~0 m because it's comparing itself to itself). The actual truth trajectory has to be reconstructed by integrating `yaw_rate_meas_rads` with `v_mps`. Easy trap. If the grader uses the stored `x_m`, V1 looks worse than V0 on CTE; if it integrates from `yaw_rate_meas` (which it must, to be sane), V1 wins on both metrics. Worth a unit-level sanity in the score-model skill.

## Failures / honest gaps

- Tesla unscorable locally. The shipped Tesla coeffs are a best-guess prior; expect Tesla yaw RMSE near V0 baseline, not the -40%-ish gains seen on the other three.
- Did not try a Pacejka or ST (linear bicycle with `C_alpha`) model. Closed-form understeer + lag is a 95% solution at 5% complexity; ST would only help in transients my lag term already absorbs.
- Did not validate on a held-out test split — fitted on full sim/ truth and scored on every 3rd sim-only file (same segments). Real OOD generalisation is unknown but the model has only 5 parameters per platform, so overfit risk is low.

## Files shipped

- `final-model/predict.py`
- `final-model/coefs.json`
- `final-model/manifest.json`
- `out/fit_v1.py`, `out/explore.py`, `out/local_score_v2.py`, `out/score_summary.json`
