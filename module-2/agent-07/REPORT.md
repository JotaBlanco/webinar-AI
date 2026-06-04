# REPORT — module-2.v3 / agent-07

## Headline result

| metric | V0 baseline | V2 shipped | improvement |
|---|---|---|---|
| **yaw_rate_rmse** (rad/s) | 0.012934 | **0.006314** | -51.2% |
| **cte_rmse** (m) | 163.83 | **78.67** | -52.0% |
| signed-bias flags | 4 (F150, Hyundai both yaw + CTE) | 0 — all platforms ok | cleared |

Scored across all 1,996 segments / 5.19M samples; 0 failures on the sim-only input-only mirror.

## What I implemented

- **V0 (baseline)**: KS-bicycle passthrough `yaw_rate_pred_rads` from sim.csv. Reproduced.
- **V2 (shipped)**: per-platform understeer-corrected single-track with steering-rate lead.
  `yaw_pred = gain * v * ((δ - δ_off) + τ · dδ/dt) / (1 + K_us · v²)`. Coefficients fit by L-BFGS-B on ~200k v-filtered samples per platform with physical bounds. Tesla is a passthrough (its sim has no independent truth — `psi_dot_rads` IS the V0 output, per the schema note in `score.py`).
- **V3 (tried, not shipped)**: added cubic-δ understeer and `v²·dδ` velocity-dependent lead. Yaw RMSE dropped to 0.006042 (-4.3%) but CTE regressed slightly to 79.44 m. Since CTE is the more sensitive trajectory metric, I kept V2.

Residual diagnostics post-V2 showed Mach-E still has structure in δ and dδ (corr ≈ -0.32, +0.27), and lag-1 autocorr stays ≈0.99 for everyone — there's headroom for a proper dynamic (first-order lag) tyre model, but I ran out of budget to do it without risking a CTE regression.

## Files shipped at `final-model/`

- `predict.py` exporting `predict(sim_df, platform) -> DataFrame`
- `coeffs.json` per-platform fitted coefficients
- `manifest.json` with `platform_support` and `predict_callable: "predict.py:predict"`

Pre-flight passes all relevant contract checks (predict importable, signature correct, shape correct on sim-only sample). Only "fail" is the optional `final-model/REPORT.md` which isn't required by the task spec.

## Most painful absent component

The harness inventory lists `fit-model` in AGENTS.md, but it's not present under `skills/` (only the 10 enumerated). I rebuilt the parametric fitter inline in `out/fit_v1.py` — fine, but I had to re-implement the train/dev gap inspection, bias bounds, and warnings that AGENTS.md describes the skill as already doing. ~10 minutes spent on plumbing that the documented skill would have given me for free.

## What the rules prevented

I caught myself wanting to peek at `module-2.v3/agent-06` (visible in `git status`) to see what tau range previous attempts used. I didn't. Initial bound was a guess; ended up landing in `tau ∈ [-0.07, 0.0]` which feels right — but I'd have been faster with a known-good prior.

## Most surprising thing

The signed steering-rate lead coefficient `τ` came out *negative* (~-0.06 s for F150 and Hyundai, ~0 for Mach-E) — meaning the model wants to *reduce* effective δ when steering is increasing. That's not a tyre-lag story (which would predict positive τ — yaw lags steering). It's most likely a phase-mismatch in the pipeline: the *measured* yaw rate lags the *measured* steering by a CAN-bus / IMU sample-time offset of ~60 ms. AGENTS.md predicted exactly this ("steering measurement and yaw measurement have different pipeline delays"), but I expected the sign opposite. F150 and Hyundai land at the same ~0.06 s; Mach-E doesn't — interesting that the Mach-E pipeline appears better-aligned than the other two.

```
ISOLATION_REPORT:
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "All reads confined to agent-07 subtree and its code/data symlinks; writes only to agent-07/out and agent-07/final-model."
```
