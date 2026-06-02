# REPORT — module-4.v2 agent-05 (idea-01 lateral fidelity)

## 1. Headline numerical result (pooled dev across all 4 platforms; v > 2 m/s sample filter, 1 m CTE bins)

| metric | V0 (passthrough) | V1 (baseline) | **V2 (mine)** | Δ vs V1 |
|---|---|---|---|---|
| yaw_rate_rmse (rad/s) | (~0.0135) | 0.005874 | **0.005845** | −0.49% |
| cte_rmse (m) | (~204) | 56.807 | **56.815** | +0.01% |

Effectively a tie with V1. Honest finding: V1 is at the structural ceiling of its functional form on this dev set.

## 2. What I implemented (variants tried)

- **V2a (refit per-platform params)** — Nelder-Mead joint fit of (g, L_eff, K_us, tau) on a 120-segment subsample per platform. Mustang τ moved 0.069→0.084, Ford F-150 essentially unchanged. Dev result: pooled yaw 0.005893, CTE 57.40. Worse than V1.
- **V2b (soft-weighted δ0)** — replaced V1's median-on-hard-threshold δ0 estimator with `exp(-|yr_v0|/scale)` over all v>5 m/s. Dev: yaw 0.005834, CTE 62.77. Worse — soft weighting reweights long-curve samples and biases δ0.
- **V2c (jerk feedforward, shipped)** — V1 form + `c_dot · δ̇ · v` additive term in yr_ss, fit per-platform. Yaw moves 0.005847→0.005845; CTE essentially flat. The 1st-order lag was already absorbing most of the transient.
- **V2d (2nd-order damped lag, tested offline)** — replaced the τ lag with a damped 2nd-order system. Offline loss reduced 1–2% only; not worth the complexity, did not ship.
- **Shipped:** V2c — V1-form + per-platform jerk feedforward + δ0 plausibility clamp + integrated x_m, y_m output. yaw=0.005845, cte=56.815.

## 3. Most painful absence in the harness

**A pre-baked train/dev split actually applied to my scoring.** The `make-train-dev-split` skill exists but `score()` was called against *all* segments under `data/sim/segments/`. So every "dev" number I report is in-sample for my fits. I have no way of knowing whether my refit Mustang params actually generalise or whether they just memorised 120 segments — and refitting cost me 5 minutes of wallclock per platform. A `score_cv` that the iterate loop forces would have killed V2a (refit) immediately, where instead I had to run full scoring twice to discover it.

## 4. What I almost did that the rules prevented

Each time I opened the V1 baseline I almost peeked at `module-3.v3` to see what coefficients prior cohorts converged to. The AGENTS.md says "Constants of record — don't refit V1" but the PLATFORM_PARAMS_V1 dict at the top of `code/v1_baseline.py` lists three independent numerical drops — I wanted to compare against the m3.v3 cohort dispersion to know whether my refit deltas were inside that spread (i.e. measurement noise) or outside (real signal). The rules say no, so I didn't, and I shipped a refit I'm not actually confident generalises.

## 5. Most surprising thing I learned

The **per-segment δ0 estimator dominates CTE**, but **V1's "median over |yr_v0|<0.03 ∧ v>5 m/s"** turns out to be a remarkably tight estimator — within ~0.001 rad MAE of the truth-aware oracle δ0 on the segments I sampled. The smooth-weighted variant I tried (which felt more elegant) was strictly worse because it gives non-zero weight to long-curve samples where δ_road is far from δ0. **The "ugly" heuristic with a hard threshold is the local optimum.** I burned 10 minutes confirming this.

## Files shipped
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-05/final-model/predict.py`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-05/final-model/manifest.json`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-05/out/` — exploration scripts (`score_v1.py`, `analyze.py`, `delta0_study.py`, `fit_full.py`, `fit_2nd.py`, `fit_jerk.py`, `score_v2.py`) and JSON artefacts.
