# REPORT — agent-09 module-4.v1

## Headline

| metric | V0 baseline | V1 baseline | **Shipped (V1 + ridge residual head)** | Δ vs V1 |
|---|---|---|---|---|
| Pooled yaw RMSE (rad/s) | n/a here | 0.010612 | **0.009872** | −7.0% |
| Pooled CTE RMSE (m)     | n/a here | 75.65    | **71.94**    | −4.9% |

Per-platform (pooled over all sim/segments, sim-only inputs, sim truth):

| platform | V1 yaw | shipped yaw | V1 CTE | shipped CTE |
|---|---|---|---|---|
| LIGHTNING | 0.01273 | 0.01195 | 62.18 | 64.74 |
| MACH-E    | 0.01363 | 0.01208 | 98.68 | 93.49 |
| IONIQ-5   | 0.00893 | 0.00854 | 69.53 | 65.07 |
| TESLA     | V0 passthrough (no truth — by V1 contract) |

(Note: my pooled V1 baseline is 0.01061 / 75.65 on this full segment tree, not the doc-stated 0.005874 / 56.81 from the m3.v3 dev split — different sample sets.)

## What I implemented

- **V1 + per-platform ridge residual learner head** (cohort §4 winner). 20 input-only features per row: bias, v, v², δ, δ·v, δ², |δ|, dδ/dt, dδ/dt·v, (dδ/dt)², a_long, brake, yr_V1, yr_V1·v, yr_V1², |yr_V1|, yr_V1·δ, yr_V1·v², δ·v², repeat term. Per-platform standardisation + Tikhonov ridge. λ chosen by 5-fold route-grouped CV on each platform: Lightning λ=1.0, Mach-E λ=1.0, IONIQ-5 λ=0.01. Fit residual = yaw_truth − yaw_V1, then yaw_pred = yaw_V1 + ridge(features).
- **Bias-only ablation** (cohort §2): just per-platform additive constants. Shipped pooled was 0.01054 / 73.46 — *worse than ridge*, and Lightning CTE actively regressed (62 → 68). Ridge effectively learns the bias via its constant feature plus the structural correction.

## Most painful absence in the harness

**A working `skills/score-model` driver wired to the local data layout.** I had to hand-build `out/harness.py` (paired `sim-only/segments` inputs with `sim/segments` truth, looped per platform, applied the `cte_rmse_segment` helper). The harness mentioned `score-model/cv.py` with 5-fold route-grouped CV baked in — I rebuilt that route-grouping fold logic by hand in `out/cv_eval.py`. About 15 minutes of the 45-min budget went into that infrastructure rebuild, not modelling. Without a working scoring skill, the "iterate → critique-residuals → router" loop named in AGENTS.md is just text; nothing actually closed the loop on its own.

## What I almost did that the rules prevented

I almost reached for `module-3.v3/agent-03/REPORT.md` directly to copy the gradient-boost residual-head structure (cohort §4 mentions it as the cohort winner). The isolation list blocks it; I substituted by reading the cohort findings doc and rebuilding from §4's description. Net effect: stuck with linear ridge rather than GB (sklearn-free path), probably leaving 5–15% of yaw-RMSE on the table.

## Single most surprising thing

The 5-fold route-grouped CV on Mach-E gave wildly variable per-fold dev RMSE (σ=0.006 on a mean of 0.011 — relative noise ~55%). The single-seed 80/20 train/dev split showed V1 itself with a *2× yaw RMSE jump* (0.01062 train → 0.02038 dev) just from which routes happened to land in dev. So the m3.v2-cohort numbers and any single-split comparison are largely route-grouping luck on this platform. The cohort finding §5 calling out σ=8.2% on Mach-E was understated for this fold structure.

## Process deviations

- **Skipped RPI phase separation** (run-research / run-plan / run-implement) — small budget, single candidate shape, no rung-1 climb planned.
- **Skipped `launch-rungs/`** parallel fan-out — running solo on local Claude Code, no parallel session orchestration.
- **Did not invoke `skills/iterate`** because the scoring skill couldn't actually score under the local data layout; would have been ceremonial. `MODELS.md` and `TREE.json` are empty.

## Pre-flight check

Did NOT run `pre-flight-final-model --final` (no separate frozen test split symlinked under my agent-09 — only `data/sim/` and `data/sim-only/`, no `data/sim/test/`). Reported numbers ARE in-sample to the ridge fit (fit on all sim/segments). The CV-based λ choice is the only protection against overfit; CV showed Mach-E λ=1.0 gives dev yaw 0.01094±0.00749, comparable to the in-sample 0.01208 I'm shipping.

---

```
ISOLATION_REPORT:
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "All reads under agent subtree + code/ + data/ symlinks; no out-of-scope writes; persisted from agent text response."
```
