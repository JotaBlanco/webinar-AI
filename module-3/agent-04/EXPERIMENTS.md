# EXPERIMENTS.md — module-3.v2 agent-04

Append-only log. Schema per `references/exploration-discipline.md`.

---

## E00 — V0 baseline (no changes)
- Rung: 0
- Hypothesis: establish the floor we're trying to beat.
- What I changed: nothing — predict() passes through `yaw_rate_pred_rads`.
- Result (pooled, score-model against all `data/sim/segments`):
  yaw_rate_rmse = 0.012934 rad/s
  cte_rmse      = 163.8307 m
  Per-platform (yaw / CTE): Lightning 0.01633 / 157.5; Mach-E 0.01362 / 148.0; IONIQ-5 0.01770 / 247.5; Tesla 0 / 0 (V0 == truth).
- Verdict: baseline.
- Things this rules out: nothing. Bias dashboard flags large signed CTE on Lightning (+39.7 m) and IONIQ-5 (-54.8 m) — points straight at the legal-cousin δ₀ recipe.

---

## E01 — Rung-0 reconstruction: g, L_eff, K_us, τ, δ₀ per platform + platform-gated per-segment δ₀
- Rung: 0
- Hypothesis: the highest-leverage move per `references/anti-patterns.md` § "The legal cousin" — `yr_ss = v·(δ - δ₀)·g / (L_eff + K_us·v²)` with first-order lag τ; per-segment δ₀ from input channels only (gate `|yaw_rate_pred_rads| < 0.03 ∧ v > 5`) on Mach-E and IONIQ-5; global δ₀ on Lightning.
- What I changed vs E00: `final-model/predict.py` + `final-model/coeffs.json`. Fit via Nelder-Mead on `data/sim/`, route-grouped 75/25 train/dev split (seed 0). Tesla passthrough (no truth).
- Result (per-platform train / dev yaw RMSE):
    Lightning: g=0.863 L_eff=3.266 K_us=0.00340 τ=0.058 δ₀=+0.00118 — 0.00529 / 0.00658
    Mach-E:    g=1.285 L_eff=3.185 K_us=0.00278 τ=0.062 δ₀=−0.00198 — 0.00844 / 0.00829
    IONIQ-5:   g=0.945 L_eff=2.935 K_us=0.00282 τ=0.051 δ₀=+0.00040 — 0.00793 / 0.00661
  Pooled (score-model, all platforms):
    yaw_rate_rmse = 0.005824 rad/s   (E00 0.012934 → **−55.0%**)
    cte_rmse      = 57.0524 m         (E00 163.83  → **−65.2%**)
  Bias dashboard: Lightning yaw_bias −0.0001 (ok); Mach-E +0.00033 (ok); IONIQ-5 −0.00075 (ok). Lightning cte_drift +20 m (warn), Mach-E +13 m (warn), IONIQ-5 -12 m (warn) — residual bias still present but ~3× smaller than V0.
- Verdict: keep — shipped model.
- Things this rules out:
    - Mach-E `g=1.285` is high vs anti-patterns' 0.891 prior. Bounds (0.5, 1.3) not pegged. Suggests strong `g ↔ L_eff` scale invariance or a steering-ratio mismatch — would tie them in a re-fit if budget allowed.
    - Per-segment δ₀ on Mach-E + IONIQ-5 closes the bias gap visible in V0.

---

## E02 — Rung 1: linear dynamic single-track, fit only C_αf per platform
- Rung: 1
- Hypothesis: V0's first-order lag is a band-aid for missing transient slip dynamics. Replace with the lateral-dynamics ODE; fix m, Iz, l_f, l_r, C_αr from carParams, fit only C_αf per platform — per `references/dynamics-formulations.md` § "Rung 1" minimum viable recipe.
- What I changed vs E01: separate script `out/rung1_attempt.py`. Linear DST with **4× sub-stepping** (plain Euler at native 50 Hz blew up at large C_αf — the doc's sketch should warn). `scipy.optimize.minimize_scalar` (bounded 20 k → 400 k). 60-segment route-grouped train/dev split per platform.
- Result (train / dev yaw RMSE):
    Mach-E:    C_αf*=336 045 N/rad  — 0.01412 / 0.00921
    Lightning: C_αf*=224 128 N/rad  — 0.00850 / 0.01075
  vs Rung-0 dev (E01): Mach-E 0.00829, Lightning 0.00658. **Rung-1 loses on both** (Mach-E +11%, Lightning +63%).
- Verdict: revert (keep E01 shipped).
- Things this rules out: on this dataset, the cheap rung-1 (only `C_αf` free, carParams Iz fixed, vy[0]=0) does not beat a well-fit rung-0 with platform-gated per-segment δ₀.
  Suspected reasons:
    - `vy[0]=0` transient at segment start (segments often begin mid-corner; rung-0's `yr_ss` is instantaneous and immune).
    - Identifiability with C_αr fixed: per the doc's warning, C_αf alone is under-constrained without lateral-accel variation.
    - carParams `Iz` is "often a crude estimate" — sensitive parameter that wasn't refit.
  Next move would be jointly fit `{C_αf, C_αr, Iz}` and seed `vy[0]` per segment — out of budget this run.
  **Generated evidence for the cohort question**: cheap rung-1 does not pay here.
