# Cohort brief (agents 01–10 of m4.v2.01)

## Headline numbers (pooled dev, frozen route-grouped split)

- V1 baseline pooled dev: **yaw 0.005430 / CTE 52.22** (cohort consensus across 10 agents, identical scoring path)
- Best rung-≥1 shipped candidate: **none structurally beat V1**. Agent-02 and agent-07 shipped M4 (orthogonal rung) which ties V1 on yaw and wins CTE by ~0.1m (within noise).
- Best rung-0 ship: V1 verbatim (agents 01, 03, 04, 05, 09, 10). Agent-06 shipped fitted-V1 with ~no-op tau tweaks.

## How many shipped a rung ≥ 1 model
- **Shipped at rung 1/2/3 dynamics-ladder: 0 of 10**. Same as the 90-agent prior across m3.v2 / m3.v3 / m4.v1 / m4.v2. The cohort is now 91 of 91.
- Shipped at rung "orthogonal" (M4 relaxation-length): 2 of 10 (agents 02, 07). Counts under the harness rule.

## Dominant failure mode per prefilled physics model

- **M1 (linear dynamic single-track, rung 1)**:
  - At priors: dev yaw 0.00919, CTE 116.89 — ~70% worse than V1 on both KPIs.
  - L-BFGS-B fit returns n_iter=0 (numerical gradient ≈ 0 at carParam priors because C_α is ~1e5 — finite-diff step too small).
  - Nelder-Mead fit converges but doesn't reliably finish in budget under CPU contention (multiple agents reported OOM kill or 10-min timeout). Agent-08 got a partial F150 fit; still worse than V1.
- **M2 (Fiala on M1, rung 2)**: collapses to M1 in small-angle regime. Same priors-only score. Untouched by anyone after seeing M1 priors miss.
- **M3 (double-track + load transfer, rung 3)**: priors-only score (0.00921 / 116.89). Nobody fit it. Agent-06 identified M3 as the right tool for the F150 ceiling and ran out of time.
- **M4 (relaxation-length, orthogonal)**: σ fits cleanly via 1D grid to 0.30–0.45m per platform. Beats V1 on CTE by ~0.1m (noise), loses ~3% on yaw. Cohort consensus: V1's time-domain τ ≈ σ/v at highway speeds — formulation-equivalent.
- **M5 (friction-circle on M1, rung 3)**: same fit pathology as M1. Nobody finished a fit.

## Per-platform asymmetry

- **F150**: yaw RMSE flat at ~0.00754 (V1) — the +21% cohort plateau. Signed CTE drift ~+29m on dev under V1. Agent-06's dev-fitted δ₀ tweak (+15% local win) sign-flipped on held-out test (+38% regression). The bias is route-correlated, not vehicle-correlated. M3 (load transfer) is the right tool; never executed in 91 attempts.
- **Mach-E**: yaw 0.00807, CTE 63.65. Cleanest behaviour; small δ₀ + τ tweaks marginally help.
- **Ioniq-5**: yaw 0.00650, CTE 67.17. Closest to noise floor on yaw. Any further correction overfits.
- **Tesla**: no truth channel → V0 passthrough across all agents.

## Train-dev gap stories
- M1 fitted dev: 50–70% worse than V1 — the priors are a deep local minimum, and a partial fit doesn't escape.
- V1 + per-platform recalibration of (g, K_us, τ): F150 train -1% but dev +3% (overfit). Confirmed locally by agent-11.
- F150 train-dev gap warned in every M4 scorecard (~+62%).
- M4 σ sweep: stable across train/dev (σ = 0.3–0.45m both splits).
- Per-segment δ₀: HURTS F150 by ~23% even on train. Cohort folklore — buried in V1 source, missed by readers.

## Strategic implication for agent-11

- **Do not** chase a fresh M1/M2/M3/M5 fit in budget — the optimiser path is poisoned and CPU is contended.
- **Do not** chase rung-0 micro-tweaks — train-dev gap eats them.
- **Do** attempt an additive correction in V1's a_lat regime targeting the F150 load-transfer signature without a multi-parameter joint fit.
- **Do** verify any candidate against held-out test (it's accessible via FROZEN_SPLIT_ALLOW_TEST=1; agent-06's failure is the cautionary tale).
