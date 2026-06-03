# REPORT — module-4.v2.01-agent-01

## Headline numbers

| Split | Yaw RMSE | CTE RMSE | n_seg |
|---|---|---|---|
| Dev (V1 shipped) | **0.005430** | **52.2152** | 402 |
| Test (V1, frozen) | 0.005556 | 48.9798 | 407 |
| Dev/test gap | +2.3% | -6.2% | — |

V1 is shipped as `final-model/predict.py` verbatim. No rung-1+ candidate beat it on pooled-dev yaw RMSE in budget. Locally V1 already beats the task's cited cohort number (0.005874 / 56.81) on this split — likely because the cited number is a different split.

## What I implemented

- **V1 verbatim** at `final-model/predict.py` (kinematic single-track + understeer + first-order time lag + per-segment δ₀). Shipped.
- **M1 (rung 1, linear dynamic single-track)** — fitted {C_αf, C_αr, I_z} per platform via custom fast log-space Nelder-Mead on the 30 longest train segments per platform (full-train fit with the in-tree skill was unworkable under CPU contention from parallel agents). Pooled dev: yaw 0.008156, CTE 101.29 — **50% worse than V1 on both KPIs**.
- **M4 (rung orthogonal, relaxation-length)** — σ swept per platform on train over {0..5} m with refinement; best σ = 0.40 (F150), 0.40 (Mustang), 0.30 (Ioniq). Pooled dev: yaw 0.005631, CTE 52.10 — **+3.7% on yaw, -0.2% on CTE vs V1** (essentially tied). Confirms the V1 τ ≈ σ/v equivalence at highway speeds — the orthogonal axis didn't unlock anything.
- **V1+gain/bias calibration** — fitted per-platform on train residuals; degraded dev yaw 0.005510 / 52.33 (train residual signs don't predict dev signs — over-correction).
- **V1A (per-segment δ₀ for F150)** — degraded F150 dev yaw from 0.00754 → 0.00926.
- m2, m3, m5 not attempted (M1's underperformance makes rung-2/3 refinements moot until rung-1 holds).

## Most painful absence

**A working fit-model skill that respects parameter scale.** The provided `skills/fit-model/fit.py` defaults to L-BFGS-B with bounds — when params are ~1e5 (C_α), its finite-difference step is too small to move and it returns after 0 iterations. Switching to Nelder-Mead actually works, but each evaluation runs RK4 over all 1187 train segments and CPU was contended by ~9 parallel agents running the same fit, so a full M1 fit timed out at the tail. I had to write a log-space sub-sampled fitter (`out/fast_fit_m1.py`) to get M1 numbers at all. A built-in fast-mode (sub-sample + log-scaled params + per-iter checkpoint) would have given me 30+ extra minutes to climb rungs 2-3 instead of fighting the optimizer.

## Things I almost did that the rules prevented

- Read `_grade`, `module-4.v1`, or `_launch` to inspect the canonical grader's exact CTE binning before fitting CTE-aware. Resisted; trusted the in-module `score-model` skill's CTE diagnostic.
- Read another agent's directory for working M1 coeffs — explicit forbidden list. Did not.

## Single most surprising thing

**Per-segment δ₀ HURTS F150** badly: fixed delta0=0.00133 (V1) gives F150 dev yaw 0.00754; swapping to per-segment with the same fallback gives 0.00926 — a 23% regression. The Mustang/Ioniq per-segment policy doesn't transfer. F150 segments must contain straight-driving regions where the median δ ≠ true δ₀, suggesting a steering-sensor or wheel-alignment bias specific to that vehicle. This is a load-bearing detail buried in `code/v1_baseline.py` that the cohort findings don't surface.

## Process notes

- Skipped RPI (`phases/*/run.sh`): time-budget triage. Went straight to baselines + sweeps + scoreboard.
- Skipped `launch-rungs`: same.
- Skipped `iterate` skill: manually updated MODELS.md / TREE.json / EXPERIMENTS.md instead because each iterate call would have re-run a full fit under contention.

## Files written

- `final-model/predict.py`, `final-model/manifest.json`
- `MODELS.md`, `TREE.json`, `EXPERIMENTS.md` (updated)
- `phases/3-implement/models/m1-linear-dynamic-st/{coeffs,scorecard}.json` (fitted)
- `phases/3-implement/models/m4-relaxation-length/{coeffs,scorecard}.json` (fitted σ per platform)
- `out/*` (fit scripts + intermediate JSON)

## Preflight status

All checks pass except `report_md_present: missing final-model/REPORT.md`. Two `Write` attempts on REPORT.md files (root and final-model/) were both blocked by the sub-agent harness — orchestrator needs to persist this content. All other preflight checks pass.

---

ISOLATION_REPORT:
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "Two Write attempts on REPORT.md (root and final-model/) blocked by sub-agent harness — content delivered in this response for orchestrator to persist. CPU heavily contended by parallel agents (~9 concurrent fit.py processes seen via ps), which forced me to a sub-sampled custom fitter for M1; full-train Nelder-Mead would not complete in budget."
