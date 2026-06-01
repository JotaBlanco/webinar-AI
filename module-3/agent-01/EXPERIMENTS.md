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

## E00 — V0 baseline (passthrough)
- Hypothesis: establish the floor we're trying to beat.
- What I changed vs nothing: nothing — predict() passes through `yaw_rate_pred_rads`.
- Result (full scorer, all platforms): yaw 0.012934; CTE 163.83.
- Per-platform: Lightning yaw=0.01633 cte=157.5; Mach-E yaw=0.01362 cte=148.0; Hyundai yaw=0.01770 cte=247.5; Tesla 0 (passthrough).
- Verdict: baseline.

## E01 — anti-patterns recipe (KS+understeer+lag+per-segment delta0) with prior coefs
- Hypothesis: the recipe in references/anti-patterns.md "Legal cousin" gave m3-agent-09 +51.8% CTE on Ford; should generalise.
- What I changed: predict() uses bicycle (g, L_eff, K_us, tau) per platform with platform-gated per-segment delta0. Replaced a_lat_meas_mps2 detector (not in allowed-input list) with yaw_rate_pred_rads<0.02 + v>5 detector. Used the doc's coeffs for Ford; Hyundai got a hand-guessed (g=0.9, L=2.9, K_us=0.0025, tau=0.065) set.
- Result: yaw 0.005999 (-54%); CTE 64.85 (-60%).
- Per-platform: Lightning yaw=0.00566 cte=62.18; Mach-E yaw=0.00822 cte=101.38; Hyundai yaw=0.00803 cte=85.79.
- Verdict: keep structure; Hyundai needs fitting.

## E02 — fit-model L-BFGS-B on yaw_plus_cte (all 3 platforms)
- Hypothesis: per-platform calibration via scipy will beat hand-set coefs, especially for Hyundai.
- What I changed: ran skills/fit-model on 50/60 train + 20 dev segs per platform with bounds.
- Result (full scorer): yaw 0.006268; CTE 65.64.
- Verdict: REVERT for Ford. Lightning fit converged near the doc's prior; Mach-E fit pushed K_us toward 0 and degraded both metrics on full eval (overfit small train sample). Keep ONLY the Hyundai coeffs.

## E03 — keep prior Ford coeffs + fitted Hyundai
- What I changed vs E02: Ford rows revert to doc coeffs; Hyundai gets fitted set (g=0.938, L=2.887, K_us=0.00289, tau=0.0619).
- Result: yaw 0.005817; CTE 64.77. Hyundai cte 85.79 -> 85.62 (small).
- Verdict: keep.

## E04 — widen straight-detector threshold for per-segment delta0
- Hypothesis: yaw_rate_pred_rads<0.02 is too tight as a "driving straight" gate when V0 itself is biased; more straight rows -> better delta0 estimate.
- What I changed: bumped yr_thresh from 0.02 to 0.03 in _per_segment_delta0().
- Result: yaw 0.005844; CTE 57.33 (Hyundai cte 85.62 -> 69.54, Mach-E cte unchanged ~101.2). HUGE Hyundai CTE win.
- Verdict: keep. Bigger gate => more straight-row coverage and a more stable per-segment median.

## E05 — Mach-E K_us tuning grid
- Hypothesis: Mach-E's CTE residual is dominated by understeer mis-calibration at the prior K_us=0.002 value.
- What I changed: scanned K_us in {0.0005, 0.001, 0.0015, 0.002, 0.003} with g=0.891, L=2.22, tau=0.069.
- Result: K_us=0.0015 best (Mach-E cte 98.68, yaw 0.00859).
- Verdict: keep K_us=0.0015 for Mach-E. Marginal — 2.5 m CTE on pooled, 1.4% improvement.

## FINAL — shipped to final-model/
- yaw_rate_rmse: 0.005874 rad/s (V0=0.012934, -54.6%)
- cte_rmse:     56.81 m       (V0=163.83,    -65.3%)
- Mach-E remains the weakest link (cte 98.7, yaw 0.0086). Worst-CTE route 00000000--33439c2a9c (5 Mach-E segments, ~340 m CTE) is a candidate for follow-up.
- Tesla passthrough (no truth channel).
