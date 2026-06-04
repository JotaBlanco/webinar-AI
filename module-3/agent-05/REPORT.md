# Module 3.v2 — Agent 05 — Lateral fidelity report

## Headline (scored over all 1996 segments in data/sim/)
- **yaw_rate_rmse: 0.005874 rad/s** (V0 baseline 0.012934 → **−54.6%**)
- **cte_rmse: 56.81 m** (V0 baseline 163.83 → **−65.3%**)

Per-platform yaw_rate_rmse (V1): Lightning 0.00566, Mach-E 0.00859, Hyundai 0.00766. Tesla 0.000 (V0 passthrough — no truth channel).

Per-platform cte_rmse (V1): Lightning 62.19, Mach-E 98.68, Hyundai 69.53. Bias-warnings: Lightning yaw +0.00012/cte +0.32 (ok); Mach-E yaw +0.00118/cte +20.4 (cte warn); Hyundai yaw -0.00126/cte -3.8 (ok). Bias hot-spot is Mach-E CTE — the rung-0 ceiling is showing.

## What I implemented
- **V0** — baseline V0 passthrough. Scored as floor: 0.012934 / 163.83.
- **V1 (shipped)** — `yr_ss = v · (δ−δ₀) · g / (L_eff + K_us·v²)` + first-order yaw lag (τ), with platform-gated per-segment δ₀ from the legal-cousin straight-row gate `|yaw_rate_pred_rads|<0.03 ∧ v>5`. On for Mach-E & Hyundai, off for Lightning, V0 passthrough for Tesla. Coefficients adopted verbatim from the top-tier recipe in `references/anti-patterns.md`.
- **V2** — same shape as V1, scipy L-BFGS-B refit per-platform on ~150–170 train segments per platform (route-grouped). Pooled metrics regressed (yaw 0.006238, CTE 58.51). The refit overfit a small subset; CTE drift on Mach-E and Hyundai grew from ~0 to −22 m and −16 m signed. Reverted.
- **V3 / Rung-1 attempt** — minimum-viable linear dynamic single-track on Mach-E only (two-state Euler `(vy, yr)`, single fitted `C_af`, carParams for `m, Iz, a, b, C_ar`, per-segment δ₀ retained). Dev yaw blew up to 0.255 vs V1's 0.0081; CTE 118 vs 92. Reverted. Logged as `Rung: 1` in EXPERIMENTS.md (E03).

## Most painful absence in the harness
**`fit-model` skill is present but I didn't trust it for the inner loop** — what I most felt the lack of was a **batched/vectorised scoring path**. Each fit iteration re-runs CTE integration across 150+ segments × per-segment δ₀ recomputation. The dominant cost is the per-segment loop in `cte_diagnostics_segment`, not optimisation steps. With a `score_batch(predict_fn, segments)` that pre-extracted arrays once and only re-ran the per-iteration cheap math, the V2 fit could have used the full 800-segment Hyundai pool and might have actually generalised. Instead I subsampled to 200 and the refit memorised the subsample.

## What I almost did that the rules prevented
- I almost wrote a per-segment δ₀ that used `yaw_rate_meas_rads` for the straight-row gate "just for local scoring, I'll swap it later." The schema check + the AGENTS.md operating contract + the existing legal-cousin recipe made the substitution obvious from the start. Without those guardrails I would have shipped a model that worked locally on `data/sim/` and failed `sim-only/` preflight.
- I almost spent time fitting a Tesla model on data with no truth channel until the schema dashboard surfaced `truth_col=psi_dot_rads` ≡ V0 baseline.

## Single most surprising thing
**The "min viable Rung 1" recipe in `references/dynamics-formulations.md` is misleading on this dataset.** It claims ~30 lines, one parameter, "even if it doesn't beat your rung-0 model, log it." In practice, naive Euler-integrated linear DST without the V0 lag term is *catastrophically* worse than V1 (dev yaw 0.255 vs 0.008 — 30× worse, not "doesn't quite beat"). The transient regime that's supposed to motivate Rung 1 is exactly where the integrator overshoots and the optimiser can't recover by adjusting C_af alone. To make Rung 1 actually competitive you'd need RK4, joint (C_af, C_ar) fit, retained first-order lag on top, and probably vy[0] initialisation per segment. That's a half-day rung climb, not 30 lines. **Cohort evidence: the cheap recipe is not a free climb.**

## Files
- `final-model/predict.py` — shipped predict.
- `final-model/manifest.json` — platform_support = [Lightning, Mach-E, Hyundai, Tesla].
- `final-model/coeffs.json` — coefficients for traceability (constants baked into predict.py).
- `final-model/REPORT.md` — short pointer to this report.
- `EXPERIMENTS.md` — E00 V0, E01 V1, E02 V2 refit (reverted), **E03 Rung 1** (reverted) — climb requirement satisfied.
- `out/score_v0.py`, `out/score_v1.py`, `out/score_v2.py` — scorers.
- `out/fit_v2.py`, `out/coeffs.json` — V2 fit artefacts (kept for transparency).
- `out/rung1_attempt.py` — Rung 1 minimum-viable attempt.
- `out/verify_simonly.py`, `out/run_preflight.py` — contract verification (all 10 preflight checks pass).

## Honest caveats
- I trusted the published top-tier coefficients in `references/anti-patterns.md` rather than re-fitting. My V2 refit was a 20-minute attempt with a 200-segment subset; it lost to V1. A proper full-pool fit would likely shave another 5–10% off pooled CTE on Mach-E.
- V1's Mach-E CTE bias (+20 m signed mean) is the easiest remaining target. A polynomial steering scale `g(v)` or a small route-bias correction would probably help — out of time budget.
- The Rung 1 attempt is honest evidence that the minimum-viable recipe doesn't pay; a serious Rung 1 climb (RK4, two params, lag retained) was out of budget.
