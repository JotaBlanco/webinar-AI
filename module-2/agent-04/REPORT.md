# Module 2.v3 — agent-04 — lateral fidelity

## Headline (full eval, n=1996 segments)

|        | yaw_rate_rmse (rad/s) | cte_rmse (m) |
|--------|-----------------------|--------------|
| V0     | 0.012934              | 163.83       |
| V1     | 0.006885              |  76.65       |
| **V2 (shipped)** | **0.006527** | **76.72** |

Per-platform after V2 (truth-bearing platforms only):
- FORD_F_150_LIGHTNING_MK1: yaw=0.00599  cte=61.30  yaw_bias=-0.00088  cte_drift=-5.2 m
- FORD_MUSTANG_MACH_E_MK1:  yaw=0.00933  cte=121.06 yaw_bias=+0.00082  cte_drift=+7.3 m
- HYUNDAI_IONIQ_5:          yaw=0.00863  cte=102.93 yaw_bias=+0.00024  cte_drift=-0.6 m
- TESLA_MODEL_3:            passthrough (no independent truth in dataset)

V0 → V2: yaw -49.5%, CTE -53.2%.

## What was implemented

- **V1** — per-platform single-track + understeer:
  `yr = v·δ / (L_eff + Kus·v²) + bias`. Fitted with `yaw_plus_cte` objective via the
  fit-model skill, bounds enforced, route-grouped 80/20 train/dev split.
- **V2 (shipped)** — V1 + steering-rate lead term:
  `yr = v·(δ + τ·dδ/dt) / (L_eff + Kus·v²) + bias`. τ ≈ −0.05 s on every
  truth-bearing platform (the V0 baseline's yaw was time-advanced relative to truth,
  so τ < 0 retards the steering signal).
- Tesla passes through V0 because its "truth" column is V0 itself — fitting it
  inflates RMSE.

V2 wins on yaw (the structural argument from AGENTS.md was correct: residual had
transient/steady regime asymmetry, ~2× worse RMSE in transients under V1). V2 is
~flat on CTE relative to V1 (76.65 → 76.72) because CTE is now noise-dominated, not
bias-dominated, and the τ term reshuffled tiny biases across platforms.

## Most painful missing component

`residual-structure` was advertised in AGENTS.md but I never actually ran it — the
fit-model + score-model + manual regime-table loop got me to V2 from V1 by reading
the per-regime split (transient rmse 0.020 vs steady 0.009 under V1 = textbook
phase-delay signature). What I *missed* was a residual-vs-feature 2-D heatmap to
confirm that the residual is `v × dδ/dt` and not `v² × δ` (cubic) before committing
to V2's structural choice. `inspect-residuals` exists but I didn't budget time to
load it. With 30 more minutes I would have run it pre-V2 to confirm the lead-term
choice over a cubic.

## Rules-prevented near-misses

I caught myself wanting to peek at `module-2.v3/agent-01/REPORT.md` to see what the
canonical winning structure was for this task. I didn't. The point of the workshop
is to surface what *this* substrate produces, not to copy. I also noticed that
`code/` has `parameters.py` with Hyundai *not* listed in `PARAM_BY_PLATFORM` — I
inferred wheelbase from the Ioniq 5 spec (3.00 m) rather than reading the agent-03
folder's plausible mirror; the fit then converged to L_eff=3.008 m which validates
the prior.

## Single most surprising thing

τ came out **negative** on every truth-bearing platform (-0.047 to -0.062 s),
meaning the V0 baseline yaw rate was *leading* truth by ~50 ms, not lagging it. My
prior (from AGENTS.md's "steering measurement and yaw measurement have different
pipeline delays") was that I'd be adding a *lead* (positive τ) to compensate for a
*lag*. Instead, V0 is the lagged signal's *opposite* — most likely because the V0
KS model uses raw measured δ without any actuator-delay model, while real yaw rate
shows the chassis already starting to rotate before δ reaches steady-state during
transients. Same sign across F150, Mach-E, Hyundai — suggesting it's a
sensor-pipeline timing constant common to comma's data pipeline, not
platform-specific dynamics.

## Files

- `final-model/predict.py`, `final-model/coeffs.json`, `final-model/manifest.json`
- `out/predict_v0.py`, `out/predict_v1.py`, `out/predict_v2.py`
- `out/score_v0.py`, `out/score_v1.py`, `out/score_v2.py`, `out/score_v2_simonly_smoke.py`
- `out/fit_v1.py`, `out/fit_v2.py`
- `out/coeffs_v1.json`, `out/coeffs_v2.json`

Pre-flight passes every check except `report_md_present` — harness blocks `Write`
on files matching `report.*\.md$`, so this content is returned via chat for the
orchestrator to persist.

```
ISOLATION_REPORT:
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "Final REPORT.md not written by me due to harness Write-block on filenames matching report.*\\.md$ — content returned in chat for orchestrator persistence."
```
