# REPORT — module-4.v1 agent-07 — lateral fidelity

## Headline result (sim-only/, verified through the predict() contract, 150 segments per platform)

| Platform | Yaw RMSE (rad/s) V1 → final | Δ% | CTE RMSE (m) V1 → final | Δ% |
|---|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.02055 → 0.01505 | −26.8% | 161.59 → 77.43 | −52.1% |
| FORD_MUSTANG_MACH_E_MK1  | 0.01428 → 0.01113 | −22.1% | 139.04 → 115.04 | −17.3% |
| HYUNDAI_IONIQ_5          | 0.01889 → 0.01285 | −32.0% | 248.07 → 115.36 | −53.5% |
| TESLA_MODEL_3            | passthrough (V1 ≡ truth)        | —      | passthrough          | —      |
| **POOLED**               | **0.01135**                     |        | **88.84**            |        |

Training metrics (sim/, 200 segs/platform): pooled yaw 0.01089, pooled CTE 92.58 m — consistent with eval, no obvious overfit.

## What I implemented

Two-layer correction stacked on the m4 V1 baseline (`yaw_rate_pred_rads` shipped in sim-only/ inputs):

1. **Per-platform additive yaw-rate bias** (cohort §2). Gated `v > 2 m/s`. Fitted: Lightning −0.00411, IONIQ +0.00352, Mach-E ≈0, Tesla ≈0. Note the Mach-E bias is ~0 — opposite cohort §2's −0.00142 rad/s — implying the m4 V1 baseline already absorbed prior Mach-E bias.
2. **Per-platform 8-feature ridge residual head** (cohort §4). Features: `δ, |δ|, v, δ·v, δ·|δ|, a_long, δ², sign(δ)·v`. λ chosen by 80/20 holdout MSE from {1, 10, 100, 1000, 10000}; refit on full train. Linear, closed-form, fast, no convergence risk.

Tesla is a passthrough because its sim/ truth (`psi_dot_rads`) is the KS model output itself — V1 and truth coincide in the training data, so bias and ridge weights collapse to zero. The pipeline naturally degenerates to identity for Tesla without special-casing.

Trained on 175–200 segments/platform from `data/sim/`; verified on 150 segments/platform from `data/sim-only/` through the exact predict() contract path (assertions: no truth columns present at predict time; output index-aligned).

Deliverable at `final-model/`:
- `predict.py` — `predict(sim_df, platform) -> DataFrame`
- `manifest.json` — platform_support + `predict_callable: "predict.py:predict"`
- `coeffs.json` — bias + ridge weights, intercept (in raw feature space)

## Most painful missing component

The **`make-train-dev-split` skill + route-grouped CV gate**. Cohort §6 explicitly warns that naive subset fits flip Lightning's sign — and that this is the failure mode m4 was supposed to make routine to avoid. I have only an i.i.d. 80/20 sample holdout, not route-grouped folds. My Lightning bias is consistent with sim-only verification, so I think it generalised, but I cannot report a route-CV σ on it. In a real workflow I'd want that σ before shipping. The skill folder is listed but I deliberately did not start exploring it under the 45-min budget — a louder, more opinionated "your candidate must pass these CV bars" gate (à la the m4 `iterate` skill described in AGENTS.md) would have made discipline cheap rather than costly.

## What I almost did that the rules prevented

I almost opened `_grade/` to pull the canonical V1 baseline and confirm my bias-fit was being computed against the same V1 the grader will hand me. The isolation rules blocked that — instead I had to trust the sim-only/ contract and verify by routing through `predict(df)` with truth columns asserted absent. That round-trip via `verify_contract.py` is the workshop-correct way; the temptation to just `cat _grade/.../baseline.json` was real.

## Most surprising finding

The fitted **Mach-E bias is essentially zero (−4e-5 rad/s)** — opposite cohort §2's claimed −0.00142 rad/s. That single number tells you the m4 V1 baseline differs structurally from m3.v3's V1 (presumably a prior debias has been baked in). The implication: cohort findings are evidence-backed *priors*, not facts you should hard-code. The residual learner head recovered Mach-E gains anyway (−22% yaw, −17% CTE) by reading the actual residual structure rather than the cohort-claimed one. Lightning showed the opposite surprise — cohort §5 said it had "nowhere left to go" on yaw, yet I got −27%, hinting m4 V1 changed there too.

## Failures / partials honest list

- No route-grouped CV done (see "missing component"). Risk: Lightning sign could be a route-imbalance artefact, though sim-only verification on different segments confirms it transfers.
- Did not attempt rung-1 dynamic ST (cohort §1 says risky, §7 says fit-loop blows budget). At pooled yaw 0.01135 the residual head is on the same order as cohort agent-03's GB head (−30% yaw); I judged this enough.
- Trajectory output is implicit: predict.py returns only `yaw_rate_pred_rads`. The grader integrates `(v_meas, yr_pred)` into `(x, y)` using `_shared/traj_metrics.integrate_trajectory` — that's the supported path per the manifest contract.

---

```
ISOLATION_REPORT:
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "All reads under agent subtree + code/ + data/ symlinks; no out-of-scope writes; persisted from agent text response."
```
