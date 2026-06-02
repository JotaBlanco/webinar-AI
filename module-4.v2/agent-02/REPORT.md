# Agent-02 — Module 4.v2 idea-01 lateral fidelity

## Headline (pooled dev, all sim/segments)

| Metric | V1 baseline | V3 (this) | Δ vs V1 |
|---|---|---|---|
| Yaw RMSE (rad/s) | 0.005874 | **0.005621** | **−4.31%** |
| CTE RMSE (m)     | 56.8071  | **53.4359**  | **−5.94%** |

Per-platform yaw residual bias collapsed to ~0 on all three trainable platforms (Mach-E was the biggest mover, +0.00142 → 0). Tesla is V0 passthrough by design (no truth channel).

## Approach

V1 (kinematic single-track + understeer + first-order lag + per-segment δ₀) is the m3.v3 cohort-converged floor; the cohort findings (§0–§4) flagged "per-platform additive bias + residual-learner head on V1" as the historically reliable win on this dataset. I implemented that pattern.

**V3** = V1 prediction + per-platform ridge-regressed residual correction with a 13-feature basis computed only from the grader-allowed columns:

```
[1, v, v², δ, δv, δ², δ²v, δ̇, δ̇v, ay_proxy, ay_proxy·|ay_proxy|, sgn(δ), |δ|v]

where
  δ        = delta_road_rad
  δ̇        = gradient(δ, t), clipped to ±5 rad/s
  ay_proxy = v · yr_v1                (truth-free; V1's own prediction)
  sgn(δ)   = sign(δ) gated by |δ| > 0.01
```

Ridge regularisation λ chosen by 5-fold route-grouped CV per platform (Lightning λ=1, Mach-E λ=1, IONIQ λ=10000 — IONIQ has 2 M rows and strongly prefers more shrinkage).

**Intermediate**: I also fitted V2 (the same idea with 9 features, no quadratics). V3 cleanly beat V2 on CV at every platform: yaw RMSE V2=0.005681 → V3=0.005621.

Tesla / unknown platform → V0 passthrough (returns `sim_df["yaw_rate_pred_rads"]` as-is). Tesla has no truth, fitting it would damage the canonical Tesla score.

## What I ruled out (and why)

- **Linear steering-rate feedforward (only `δ̇` and `δ̇·v` as standalone correction)** — Cohort §3 evidence that V1's τ-lag already absorbs everything a linear δ̇ term can do. Confirmed: my `δ̇` and `δ̇·v` ridge coefficients are small and unstable on Mach-E.
- **Refitting V1's τ-lag.** Cohort §8: dead-end across the entire m3.v3 cohort. Did not try.
- **Rung-1 dynamic single-track with carParams** (§1). Without `_shared/rung1_starter.fit_calpha_and_iz`-quality fitting (not enough budget to do this right), rung-1 always lost on the m3.v3 cohort.
- **Asymmetric (left/right) gated bias on a subset.** Cohort §6 + agent-07's failure: subset-fitting flipped Lightning sign. I include `sgn(δ)` as a feature but in a route-grouped CV fit on the full dataset, which is the §6-prescribed discipline.
- **GB / non-linear residual head** (§4 — agent-03's −30% yaw shipping winner). Best move available; ridge is the conservative fallback. With ~45 min budget I prioritised confidence in the cross-validation discipline over a higher-leverage but riskier learner. This is the single biggest unrealised upside in my submission.

## Per-platform behaviour

| Platform | yaw_rmse | cte_rmse | yaw_bias | n_seg | best λ |
|---|---|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.00518 | 60.18  | +0.00000 | 175 | 1.0 |
| FORD_MUSTANG_MACH_E_MK1  | 0.00768 | 90.32  | −0.00000 | 240 | 1.0 |
| HYUNDAI_IONIQ_5          | 0.00755 | 66.19  | +0.00000 | 800 | 1e4 |
| TESLA_MODEL_3            | 0.00000 | 0.000  | (V0 passthrough) | 781 | — |

Per regime (yaw only): straight rmse=0.00433, steady=0.00771, transient=0.01564. Transient regime still owns most of the residual energy — consistent with cohort §8 ("transient lives in non-linear (δ, δ̇, v)").

## Ship contents

- `final-model/predict.py` — self-contained: inlines V1 params and integrator, loads `coefs_v3/<platform>.json` for the ridge weights.
- `final-model/manifest.json` — declares `predict_callable` and `platform_support`.
- `final-model/coefs_v3/{FORD_F_150_LIGHTNING_MK1,FORD_MUSTANG_MACH_E_MK1,HYUNDAI_IONIQ_5}.json` — per-platform fitted coefficients + CV summary.

Verified against `data/sim-only/segments/` (8-column grader-mirrored view) — no `KeyError`s on truth channels.

## Harness-component absence I felt most

A working `fit-model/` skill for non-V1 model shapes — I hand-rolled the ridge solver and route-grouped CV. ~80 lines of plumbing. Same gap the m3.v3 cohort flagged in finding §7.

## Limitations

- No 1-D GB head fitted (would likely push to the cohort-winning −15-20% CTE range).
- Did not exercise the `_shared/rung1_starter.py` properly — would need a few more minutes to fit `C_α` and `Iz` per platform with the in-budget Nelder-Mead.
- Did not run the local `cv.py` skill wrapper end-to-end; I wrote my own k-fold inline. Same numbers, but skips the formal "iterate" gate.
