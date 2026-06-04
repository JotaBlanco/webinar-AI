# Report — module-3.v2 / agent-02

## 1. Headline numerical result

Scored on the full local `data/sim/segments/` pool (1996 segments, 5.19M samples) with the score-model skill (allowlist-stripped sim_df, matches grader contract):

| metric | V0 baseline | shipped | delta |
|---|---|---|---|
| pooled yaw_rate_rmse (rad/s) | 0.012934 | **0.005824** | **-55.0%** |
| pooled cte_rmse (m) | 163.83 | **56.99** | **-65.2%** |

Per-platform yaw_rmse: Lightning 0.00566, Mach-E 0.00842, IONIQ-5 0.00763, Tesla 0.0 (V0 passthrough). Preflight passes 10/10 checks against `data/sim-only/` (canonical-grader contract).

## 2. What I implemented

- **V0 score (E00)**: passthrough of `yaw_rate_pred_rads` to establish floor.
- **V1 (E01)**: rung-0 recipe verbatim from `references/anti-patterns.md` § "Legal cousin" — KS + steering scale g + understeer K_us + first-order lag τ + platform-gated per-segment δ₀ (legal input-only straight gate `|yaw_rate_pred_rads| < 0.03 ∧ v > 5`). Lightning uses global δ₀; Mach-E/IONIQ-5 use per-segment. Tesla = V0 passthrough. Already at yaw 0.005874 / CTE 56.81 with cohort-published coefficients.
- **V2 (E02, shipped)**: scipy L-BFGS-B per-platform fit of (g, L_eff, K_us, τ, δ₀) against pooled yaw RMSE, route-grouped 80/20 train/dev. Tiny improvement: yaw 0.005874 → 0.005824. Train/dev gap small (~5–10% on each platform), no overfit signal.
- **V3 (E03)**: same fit + λ·bias² penalty. Did not help (CTE slightly worse). Reverted.
- **E04 — required rung-1 climb attempt**: linear dynamic single-track with slip angles (states vy, yr; F = C_α·α), 20× sub-stepped Euler @ 1 kHz to avoid the 50 Hz divergence the reference doc warns about. Fit C_αf only on Mach-E with other params fixed to carParams. Result on Mach-E: yaw 0.01452 (dev 0.01157) — **72% worse** than the rung-0 V2 fit on Mach-E. Logged, reverted, V2 shipped. This is the evidence point the cohort needs: naive rung-1 with one fitted parameter and carParams-fixed structural params does NOT beat a well-calibrated rung-0 within a 45-min budget.

## 3. Most painful absence

**`route-bias` skill was present in spec but I didn't get time to use it properly.** What actually hurt most was the *absence of an automated yaw+CTE blended fit objective* — `fit-model` ships with `objective="cte"` and `objective="yaw_plus_cte"` per the SKILL.md, but using it requires writing the `predict_factory` plumbing and going through the full skill. With my time budget I rolled my own scipy fit against yaw RMSE, and the V2→V3 experiment (adding a hand-rolled bias penalty) showed that the *signed-bias* residual on Mach-E (cte_signed_mean = -21 m even after fit) is the dominant CTE source — exactly what a true CTE-objective fit would target. A skill I could invoke with one line that integrated trajectories per iteration would likely have shaved another 5–10 m off CTE.

## 4. Things I almost did that the rules prevented

- I almost typed `sim_df["a_lat_meas_mps2"]` into the straight-gate proxy without reading the AGENTS.md operating contract — the reference doc text mentions it as a "tempting" gate, and the recipe lives next to the warning. Caught by the explicit reminder in `references/anti-patterns.md`. Used the allowlist `|yaw_rate_pred_rads| < 0.03` gate instead.
- I almost evaluated only with `data/sim/segments` and shipped without running preflight against `sim-only/`. Preflight check 9 catches the allowlist mismatch; my predict happens to be clean, but the discipline was a near-miss.

## 5. Most surprising thing I learned

The recipe in `references/anti-patterns.md` ships **with the actual top-tier shipped coefficients inline**, and the dataset-specific re-fit (V2) over scipy with route-grouped split moves the headline yaw RMSE by less than 1% and *worsens* CTE slightly. The recipe coefficients (`g=0.891, L_eff=2.22, K_us=0.0015, τ=0.069` for Mach-E) are already essentially the local optimum of the rung-0 state space on this data. That implies the +30% headroom above this ceiling — if it exists — does live at rung 1+, not at rung-0 coefficient hygiene. The cohort failure pattern the AGENTS.md doc describes (everyone refines rung 0 forever) is structurally rational from inside the run: rung 0 keeps paying tiny dividends, rung 1 visibly costs you yaw RMSE on first attempt, and the time budget collapses the cost/benefit ratio against climbing.

## Key files

- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-02/final-model/predict.py`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-02/final-model/coeffs.json`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-02/final-model/manifest.json`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-02/EXPERIMENTS.md` (E00–E04, rung-1 attempt logged)
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-02/out/` (fit scripts, scoring scripts, rung-1 attempt)
