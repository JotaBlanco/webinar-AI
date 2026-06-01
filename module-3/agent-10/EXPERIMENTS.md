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
- Result (dev, my scorer): yaw 0.01763; CTE 218.16 (pooled across 3 platforms with truth).
- Verdict: baseline.
- Things this rules out: nothing yet.

## E01 — KS + understeer + tau + δ₀ for Ford only (predict_v1)
- Hypothesis: anti-patterns recipe (m3-agent-09 worked example) applied to Ford platforms only.
- What I changed: hand-set coeffs for Lightning (global δ₀) and Mach-E (per-segment δ₀ from a_lat proxy); Hyundai left on V0.
- Result (dev): yaw 0.01620 (-8.1%); CTE 205.94 (-5.6%).
- Verdict: partial — Ford big wins, Hyundai untouched.
- Things this rules out: nothing.

## E02 — Per-platform Nelder-Mead fit on all three platforms (predict_v2 / final)
- Hypothesis: fit (g, L_eff, K_us, tau, δ₀) per platform; choose per-seg vs global δ₀ per platform.
- What I changed: vectorised fitter (`fit2.py`) caches segment arrays; minimises sample-pooled MSE on truth. Mach-E uses per-segment δ₀, Lightning & Ioniq use global δ₀.
- Result (dev): yaw **0.01085** (-38.5%); CTE **101.80** (-53.3%).
- Per-platform: Lightning yaw 0.0127 / CTE 61.0 ; Mach-E yaw 0.0135 / CTE 109.0 ; Ioniq yaw 0.0094 / CTE 106.7.
- Verdict: keep — this is the shipped model.
- Things this rules out: nothing yet.

## E03 — Wheelbase-constrained fit (fit3.py) and broader-bounds fit (fit4.py) — partial
- Hypothesis: lock L_eff to manufacturer wheelbase to remove the g×L_eff scale invariance; or relax bounds so g can exceed 1.5.
- What I changed: fit3 fixes L_eff; fit4 widens bounds (g up to 3, L_eff up to 6).
- Result: fit3 wasn't run end-to-end (time). fit4: Mach-E per-seg=True hits L_eff ceiling at 6.0, RMSE 0.01352 — essentially same as fit2's 0.01352 (per-seg). Lightning per-seg=True yielded RMSE 0.01337 — worse than fit2's global-δ₀ 0.01268.
- Verdict: revert — fit2's mix (per-seg for Mach-E, global for others) is the local optimum at this structural rung.
- Things this rules out: relaxing bounds on g/L_eff at this rung doesn't help — the residual is now structural, not parameter-noise. Climbing to a dynamic single-track (linear tyre slip) would be the next move; out of time-budget here.
