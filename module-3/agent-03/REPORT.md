# Module 3 — Agent 03 — Report (final-angle-v2 / idea-01 lateral fidelity)

**Headline (pooled across all 4 platforms / 1996 segments / sim/segments):**
- Yaw-rate RMSE: **0.01293 → 0.00586 rad/s (-54.7%)**
- Distance-resampled CTE RMSE: **163.83 → 62.83 m (-61.6%)**

Per-platform (yaw_rmse rad/s | CTE m):
- FORD_F_150_LIGHTNING_MK1: 0.01633 → 0.00570 | 157.5 → 61.4
- FORD_MUSTANG_MACH_E_MK1: 0.01362 → 0.00857 | 148.0 → 107.5
- HYUNDAI_IONIQ_5: 0.01770 → 0.00763 | 247.5 → 79.1
- TESLA_MODEL_3: 0 → 0 | 0 → 0 (V0 passthrough — no truth channel)

Preflight: 8/9 checks pass; only `REPORT.md` missing locally (orchestrator persists this).

## What I implemented
- One variant, per-platform: refined kinematic single-track `yr_ss = v·(δ−δ₀)·g / (L_eff + K_us·v²)` + first-order yaw-rate lag `τ`, fitted per platform (Nelder-Mead, composite loss `yaw/0.01 + 0.5·CTE/50`) against `data/sim/segments/`.
- Platform-gated per-segment δ₀: estimated each segment's residual steering offset from rows where `|δ_road| < 0.005 rad ∧ v > 8 m/s` (median). A/B'd ON for Mach-E & Hyundai (wide segment bias spread), OFF for Lightning (tight spread → hurts CTE from 60 → 122 m). Tesla = V0 passthrough.
- Files: `final-model/predict.py`, `final-model/coeffs.json`, `final-model/manifest.json`; fitter at `out/fit.py`; experiment log entry in `EXPERIMENTS.md`.

## Most painful absence in the harness
**No `a_lat_meas_mps2` in the sim-only operating contract.** Every published "legal cousin" recipe in `anti-patterns.md` and `approach-menu.md` uses `|a_lat_meas| < 0.3` as the straight-row detector for per-segment δ₀. That column is in `data/sim/segments/` but NOT in `ALLOWED_INPUT_COLUMNS`. I had to substitute `|delta_road_rad| < 0.005` — coarser, and circular (using steering to detect not-steering). My Mach-E CTE (107 m) is the visible cost; the canonical recipe with `a_lat_meas` reportedly hits ~75 m there. The references should either flag this or include an `a_lat_meas`-free recipe variant.

## What the rules nearly led me to do
The task says baseline yaw-rate is "pre-computed as `yaw_rate_pred_rads` in every sim.csv". It's not — the *training* `sim/segments/TESLA_MODEL_3/*/sim.csv` has `psi_dot_rads` instead (different column name; same content for Tesla because Tesla has no independent truth). I almost added a custom Tesla branch to my fitter before noticing `PLATFORM_SCHEMA` already handles the alias and that fitting Tesla is pointless (no truth). Time saved: ~10 min.

## Most surprising thing learned
Hyundai (which has no entry in `code/parameters.py` and no mention in any reference doc) responds extremely well to the same Mach-E recipe (CTE 248 → 79 m, ~68% drop) — bigger absolute and relative gain than either Ford. The references treat the problem as Mach-E vs Lightning; in fact Hyundai dominates the V0 CTE pool (800 / 1996 segments) and is where most of my "61.6% improvement" actually comes from.

## Honest gaps
- I never climbed past Rung 0 (no dynamic ST, no slip-angle model, no a_lat fusion). 45 min was tight, and the residual didn't scream "transient-regime-dominated" per the diagnostic (transient rmse=0.0165 vs steady=0.0081 — present but not isolated).
- No train/dev route-grouped split; fitted directly on a 150-segment stride of training data. Risk of overfit isn't quantified.
- Mach-E `g` fitted to 1.03 (near 1.0) and Hyundai `g`=0.90 are reasonable. Lightning hit Mach-E's L_eff bound the first run (caught and widened); Hyundai also bumped the original `L_eff` ceiling — second run with widened bound gave only marginal improvement, but worth flagging.
