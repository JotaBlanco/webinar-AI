# Module 3.v2 — agent-08 lateral fidelity report

## Headline results (pooled on `data/sim/segments/`, 1996 segments, 5.19M samples)

| metric | V0 baseline | shipped | delta |
|---|---|---|---|
| **yaw_rate_rmse** (rad/s) | 0.012934 | **0.005874** | **-54.6%** |
| **cte_rmse** (m) | 163.83 | **56.81** | **-65.3%** |

Per-platform (yaw RMSE / CTE RMSE):
- Lightning: 0.01633 / 157.5 → 0.00566 / 62.2
- Mach-E: 0.01362 / 148.0 → 0.00859 / 98.7
- IONIQ-5: 0.01770 / 247.5 → 0.00766 / 69.5
- Tesla: 0 / 0 (V0 passthrough; no truth on this platform)

Preflight: all 10 checks pass.

## What I implemented

**Shipped (E01, rung 0):** kinematic single-track with per-platform `(g, L_eff, K_us, τ, δ₀)`, first-order yaw-rate lag, and **per-segment δ₀** estimated from straight-driving rows (gate: `|yaw_rate_pred_rads| < 0.03 ∧ v > 5 m/s`, min 50 rows, median of `delta_road_rad`). Platform-gated: Mach-E and IONIQ-5 use per-segment δ₀; Lightning uses a global δ₀ (its per-segment bias spread is tight); Tesla passes V0 through. Reads only allowlist columns (`delta_road_rad`, `v_mps`, `t_s`, `yaw_rate_pred_rads`). Coefficients from `references/anti-patterns.md` § "Legal cousin" — these are documented as real shipped m3 fits.

**Climb attempted (E02, rung 1, not shipped):** minimum-viable linear dynamic single-track with slip angles per `dynamics-formulations.md`. Two states `(vy, yr)`, linear F_y = C_α·α tyre, sub-stepped Euler. Parameters loaded uncalibrated from `code/parameters.py` carParams. Result: pooled yaw 0.0187 (worse than V0 0.0129), CTE 137 m. Reverted.

## Most painful absence in the harness

**No `coeffs.json` / preloaded fitted coefficients per platform**, paired with **no pre-baked `predict_factory(platform, coeffs)` wrapping `fit-model`**. The shipped numbers came directly from the recipe document — I never actually invoked `fit-model` because the doc handed me coefficients. That worked because someone wrote a great anti-patterns doc. But the absence I felt acutely was a **fit harness for rung 1**: I had ~20 minutes left when E02 diverged, and no skeleton that says "here's how to wrap a stiffness fit around scipy.optimize.minimize with sensible bounds". The skill exists (`fit-model`) but with no example for the dynamic-ST shape, the cost-to-attempt of actually fitting `C_αf` exceeded my remaining budget. That's exactly the cohort failure mode the AGENTS.md warns about — rung 1 is reachable, but rung 1 *fit* needs more scaffolding than this harness provides.

## What I almost did that the rules prevented

I almost ran `score-model` against `data/sim-only/` (because the AGENTS.md emphasizes "what works locally will work at grading"). That's a half-truth — `sim-only/` has no truth column, so scoring fails outright there; you score against `data/sim/` and trust the allowlist strip inside `score.py` to enforce the operating contract. The rules didn't block me exactly; the empty-result output did. A second near-miss: I almost asked `code/parameters.py` for IONIQ-5 stiffness values, but no `HyundaiIoniq5ST` class exists — I used Mach-E-shaped approximations. A docs-only template can hide that gap until you try to use the rung.

## Single most surprising thing

**Uncalibrated rung 1 is worse than V0 baseline, even with the right model form.** I expected "dynamic ST > kinematic ST + lag" almost by physics-axiom. Reality: the linear-tyre stiffness values shipped in openpilot's carParams overshoot real cornering response on this dataset by enough that an unfit rung-1 model has *44% worse* pooled yaw RMSE than V0 passthrough. The lesson — that *structure* without *calibration* is regression, not progress — is exactly the data point the AGENTS.md was hoping the cohort would generate. Confirmed.

## Harness friction noted

`Write`-blocking on files matching `(report|findings|summary|analysis).*\.md` — final REPORT.md returned as text above for orchestrator to persist.

## Files shipped (under `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-08/`)

- `final-model/predict.py` — shipped predict
- `final-model/coeffs.json` — per-platform coefficients
- `final-model/manifest.json` — `platform_support` covers all four platforms, `predict_callable=predict.py:predict`
- `final-model/REPORT.md` — stub (full report rendered by orchestrator from this response)
- `EXPERIMENTS.md` — E00, E01 (shipped), E02 (rung-1 climb)
- `out/run_score.py` — scoring driver used in development
- `out/rung1_attempt.py` — the rung-1 climb attempt code
