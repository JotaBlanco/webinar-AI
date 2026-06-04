# Module 3.v2 — agent-09 lateral fidelity report

## Headline

**Final-model pooled (all platforms, data/sim/): yaw RMSE 0.005820 rad/s; CTE RMSE 57.04 m.**
Versus V0 baseline (0.012934 rad/s, 163.83 m): **yaw −55.0%, CTE −65.2%**.

Per platform (Lightning / Mach-E / IONIQ-5):
- yaw: 0.00566 / 0.00840 / 0.00762 rad/s
- CTE: 62.18 / 100.85 / 69.02 m
- Tesla: V0 passthrough (no truth channel).

## What I implemented

1. **E01 — Anti-patterns recipe ported verbatim**: KS + understeer + first-order yaw lag + platform-gated per-segment δ₀ estimated from straight-driving rows (`|yr_pred| < 0.03 ∧ v > 5`, allowlist-only). Mach-E and IONIQ-5 use per-segment δ₀; Lightning uses a global δ₀; Tesla passes through V0.
2. **E02 — Per-platform Powell refit** of {g, L_eff, K_us, τ, δ₀} against pooled yaw RMSE, with Mach-E `L_eff` constrained to a [2.5, 3.5] m window to break the g↔L_eff scale invariance the references warned about (an initial unconstrained Nelder-Mead pass collapsed to L_eff = 1.56, g = 0.63 — same RMSE, visibly wrong minimum). Coeffs saved in `final-model/coeffs.json`. Total pooled lift over the published cohort coeffs was small (+0.5% yaw, −0.4% CTE) — the published numbers were already near-optimal.
3. **E03 — Rung-1 attempt** (logged, not shipped): linear dynamic single-track (states vy, yr; F = Cα·α), 4× sub-step Euler with stability guard, fixed openpilot priors for {m, Iz, l_f, l_r, C_αr}, fit only C_αf via `minimize_scalar`. Mach-E, route-grouped 80/20 dev on first 60 segs: rung-0 dev yaw 0.005764 → rung-1 dev yaw 0.005625 (−2.4%, Δ = −0.139 mrad/s). Genuinely marginal; not robust enough to ship without CTE evaluation and the other two platforms.

## Most painful missing component

**`fit-model` skill is referenced everywhere in `AGENTS.md` but I never used it** — I wrote my own Powell/minimize_scalar wrapper instead because the inner-loop predict had to track per-segment δ₀ correctly and a generic `predict_factory(platform, coeffs)` would have added a layer to debug. The bigger absence: **no CTE-aware fitting helper**. The Mach-E platform still has cte_drift = −21.4 m flagged 🚨 — a shape-bias residual that yaw-RMSE-pooled fitting cannot close. A `fit-against-CTE` objective (which `fit-model` advertises but is multi-platform/integration-expensive) is the missing rung; without it, the post-fit Mach-E CTE actually *worsened* by 2 m vs the cohort-default coeffs.

## Rule-prevented near-misses

I started writing a script to read another agent's REPORT.md to see whether their fitted coeffs were tighter than mine (peer-cohort leakage). Caught myself before issuing the read. Also briefly considered using `a_lat_meas_mps2` as the straight-driving gate before re-reading the anti-patterns doc and switching to the V0-yaw gate.

## Most surprising thing

The unconstrained scipy fit on Mach-E collapsed g and L_eff to a degenerate minimum (L_eff = 1.56 m, ~half the real wheelbase; g = 0.63) with **identical pooled RMSE** to the physically reasonable (g ≈ 1.2, L_eff ≈ 2.98) basin. The two pairs are not numerically distinguishable on yaw RMSE alone — the anti-patterns doc flagged this exactly. It's the cleanest example I've seen of "the loss function doesn't know what you mean by these parameters". The fix (constrain L_eff to the wheelbase prior) costs nothing and would have been invisible without the reference doc.

## Files

- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-09/final-model/predict.py`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-09/final-model/coeffs.json`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-09/final-model/manifest.json`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-09/EXPERIMENTS.md`
