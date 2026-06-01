# EXPERIMENTS.md

Append-only log of approaches you tried. One entry per concrete attempt. See `references/exploration-discipline.md` for the why.

Schema:

```
## E<NN> — <one-line approach name>
- Hypothesis: why you thought this would help, in one line.
- What I changed vs E<NN-1>: the minimal diff.
- Result (dev): yaw <old> → <new> (Δ%); CTE <old> → <new> (Δ%).
- Verdict: keep | revert | revisit-later.
- Things this rules out: what you learned, even if the experiment failed.
```

Delete this header section once you start logging, but keep the schema close to mind.

---

## E00 — V0 baseline (no changes)
- Hypothesis: establish the floor we're trying to beat.
- What I changed vs nothing: nothing — predict() passes through `yaw_rate_pred_rads`.
- Result (full eval): yaw 0.01416; CTE 163.83.
  - Per-platform: Lightning yaw=0.0163/cte=157.5 (bias 🚨), Mach-E yaw=0.0136/cte=148.0 (ok), Ioniq yaw=0.0177/cte=247.5 (bias 🚨).
- Verdict: baseline.
- Things this rules out: nothing yet. Sign of pooled bias on Lightning and Ioniq says global-δ₀ / K_us calibration is the highest-leverage move.

## E01 — Rung-0 KS + understeer + lag + per-segment δ₀ (platform-gated), priors-only
- Hypothesis: anti-patterns.md's prior recipe (m3-agent-09 numbers) already lifts ~50% on this dataset; ship it before fitting.
- What I changed vs E00: predict.py implements `yr_ss = v · (δ - δ₀) · g / (L_eff + K_us·v²)` with a first-order lag.
  - Mach-E and Ioniq use input-derived per-segment δ₀ (straight detector: `|delta_road_rad| < 0.005 AND v > 5`, min 50 rows). Lightning uses global δ₀.
  - Tesla: V0 passthrough.
- Result (full eval): yaw 0.00671 (-52.6%); CTE 64.69 (-60.5%).
- Verdict: keep, target the residual bias on Mach-E and Ioniq next.
- Things this rules out: the bulk of V0's gap is bias + understeer mismatch, not transient dynamics — rung-0 closes most of it.

## E02 — Minimal Nelder-Mead refinement on `{δ₀, K_us, g, τ}` (per platform; +L_eff for Ioniq)
- Hypothesis: priors are close but not on the optimum; cheap NM over 60 train segments per platform can shave another few %.
- What I changed vs E01: refit per-platform via Nelder-Mead on a 60-segment random subsample, loss = yaw_rmse + 3e-4·cte_rmse.
- Result (full eval): yaw 0.00587 (-58.5% vs V0); CTE 63.12 (-61.5% vs V0).
- Verdict: keep. Mach-E was almost unmoved (cte 108.7 → 107.5), Ioniq improved most (yaw 0.0093 → 0.0076, cte 82.4 → 79.6), Lightning yaw slightly worse (0.00566 → 0.00598) but cte slightly better.
- Things this rules out: rung-0 ceiling on Mach-E is near here — bias of -20m signed cte_drift is persistent across all refits, suggesting it's segment-distribution-driven (a few high-CTE Mach-E outliers dominate the pool).

## Approaches named but NOT tried (per exploration-discipline.md)
1. *(rung-0, coefficient)* Polynomial g(δ) on Mach-E — referenced as the canonical Mach-E gain. Not tried; rung-0 + per-segment δ₀ already brought Mach-E to bias-of-noise levels on yaw, and the residual CTE is concentrated in <5 outlier segments rather than spread across the population.
2. *(rung-0, coefficient)* `K_us(v)` speed-dependent — small effect per ref; deferred.
3. *(rung-1, structural)* Linear dynamic single-track with slip angles — transient-regime RMSE (0.021) is 4× the straight-regime (0.0045), which is the canonical "climb a rung" signal. Did NOT try due to time budget.
4. *(rung-2, structural)* Nonlinear tyre (Pacejka/Fiala) — not tried; rung-1 was the next logical step.
5. *(orthogonal)* Residual learner on physics prior — not tried; would require route-grouped train/dev split (no `make-train-dev-split` was used).
