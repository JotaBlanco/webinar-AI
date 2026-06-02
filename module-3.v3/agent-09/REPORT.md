# REPORT — module-3.v3 agent-09

## Headline (dev pooled)

| metric | V1 floor | shipped (v1_affine) | Δ |
|---|---|---|---|
| yaw_rate_rmse (rad/s) | 0.005874 | **0.005815** | -1.0% |
| cte_rmse (m) | 56.81 | **54.48** | -4.1% |
| Mach-E CTE | 98.68 | 91.98 | -6.8% |
| IONIQ-5 CTE | 69.53 | 67.36 | -3.1% |
| Lightning CTE | 62.19 | 62.19 | 0% (passthrough) |

## Residual diagnosis (starting point)

V1's pooled CTE is dominated by signed yaw-bias-driven trajectory drift on Mach-E (-21.98 m, 🚨) and IONIQ-5 (-11.57 m, ⚠️). Mach-E's yaw residual mean is -0.00142 rad/s (sign matters for CTE: a constant bias of 1.4 milli-rad over 1.6 km of distance = ~2 m of cross-track on flat ground, but in cornering segments it compounds). Lightning is already at the noise floor.

The default story (per AGENTS.md) is that Mach-E's worst-fit comes from transient dynamics V1's first-order lag can't model. That story is partially wrong: most of the leverage is in the signed bias, not transient RMS.

## What I tried (see EXPERIMENTS.md for full log)

- **E01 (refines-v1) — per-segment δ₀ on all platforms**: lost. Lightning's fixed δ₀ is correct; per-seg median is noisier.
- **E02 (differs-from-v1) — feed-forward `k_ff · d(δ_road)/dt`**: negligible. Real but tiny effect.
- **E03 (refines-v1) — per-platform affine `s·y_v1 + b`**: WIN. Route-grouped holdout: Mach-E and IONIQ-5 keep their gains OOS; Lightning loses, so forced to passthrough.
- **E04 (differs-from-v1) — combined (s, b, k_ff)**: tied with E03. k_ff redundant after affine.
- **Not built**: rung-1 dynamic single-track. Time budget.

## What's shipped, and why

`v1_affine`: V1 with `y = s_p · y_v1 + b_p` per platform. Coefficients:
- Lightning: passthrough (1.0, 0.0)
- Mach-E: s=0.986, b=+0.00144
- IONIQ-5: s=0.994, b=+0.00073
- Tesla: V0 passthrough (no truth)

**Structural-novelty caveat**: this is `refines-v1`, not `differs-from-v1`. Preflight warns (correctly). I am explicitly shipping it because: (a) my one structurally-distinct candidate that improved (E02) had negligible gain; (b) the combined structural+refining candidate (E04) gave nothing beyond E03; (c) E03 wins by a real, holdout-confirmed margin.

## Cohort signal: what *not* to try

The "Mach-E is transient-dynamics-limited" framing in `dynamics-formulations.md` is at best half the story. A structurally novel model that doesn't first correct the signed bias will see most of its theoretical gain eaten by the constant offset V1 ships with.

## Component most missed

A rung-1 scaffold in `_shared/`. With it, the dynamic single-track candidate would have been an hour of work, not three.
