# agent-03 — Lateral Fidelity V2

## Headline

| KPI | V0 baseline | V2 (this) | Δ |
|---|---|---|---|
| Yaw RMSE (all Ford, rad/s) | 0.01479 | 0.00725 | −51% |
| CTE RMSE (all Ford, m) | 152.0 | 101.2 | −33% |
| Yaw RMSE (dev, rad/s) | 0.01302 | 0.00617 | −53% |
| CTE RMSE (dev, m) | 135.8 | 86.2 | −37% |

Per platform on the full Ford set:

| Platform | V0 yaw | V2 yaw | V0 CTE | V2 CTE |
|---|---|---|---|---|
| F-150 Lightning | 0.01633 | 0.00526 | 157.5 | 59.4 |
| Mach-E | 0.01362 | 0.00837 | 148.0 | 122.4 |

Tesla: V0 passthrough (no truth channel).

## Model

Per-platform fit on whole-route train split (75/25, stratified per platform, seed 42). For each Ford platform:

    delta_eff = g0·delta + g2·delta·|delta| + delta0
    K_eff     = K0 + K1·v
    yr_ss     = v · delta_eff / (L_eff + K_eff·v²)
    yr        = first-order-lag(yr_ss, tau)

Seven parameters per platform: `g0, g2, delta0, L_eff, K0, K1, tau`. Fit by Levenberg–Marquardt (`scipy.optimize.least_squares`) on yaw-rate residuals, weighted by `v > 3 m/s` to suppress stand-still rows.

Fitted Lightning: `g0=0.922, g2=0.159, delta0=-0.0011, L_eff=3.64m, K0=0.00477, K1=-5.9e-5, tau=74ms`.
Fitted Mach-E:    `g0=1.022, g2=0.401, delta0=+6e-5,  L_eff=2.77m, K0=0.00153, K1=+1.5e-5, tau=85ms`.

Both `L_eff` differ from the openpilot canonical wheelbases (3.70 / 2.984m) — the data wins, as warned by the anti-patterns ref. Mach-E `g2` is large (≈0.40) — strong steering nonlinearity that V1's linear scale couldn't capture.

## What I tried

- **V1**: linear steering scale `g·δ + δ₀` + closed-form understeer `K_us·v²` + tau lag. Dev: yaw 0.00679, CTE 85.1m. Big jump from V0.
- **V2 (shipped)**: V1 + odd-quadratic steering nonlinearity `g2·δ|δ|` + linear K_us drift in `v`. Mach-E yaw drops 12%, steady/transient regime errors improve cleanly. CTE roughly unchanged from V1, but yaw-RMSE win is real.

## Skills + references used

- **make-train-dev-split**: as-is — whole-route, per-platform stratified, seed 42.
- **score-model**: as-is — pooled yaw RMSE (`v>2`), pooled CTE on segs ≥ 20m, 1m grid.
- **pre-flight-final-model**: invoked at end — all 8 functional checks pass; only REPORT.md flagged (harness-blocked).
- **compare-models / load-segments / visualise-segment**: SKILL.md inspected, bodies not loaded.
- **anti-patterns.md**: shaped the fit. Per-platform, whole-route, no per-segment bias hack, bounds widened past openpilot priors.
- **approach-menu.md**: flagged polynomial steering and speed-dep K_us as [unexplored] — both gave gains, especially on Mach-E and in the steady/transient regimes.
- **two-kpi-tradeoff.md**: diagnosed Mach-E residual as bias-shaped (yaw improves more than CTE).

## Honest limitations

- Mach-E CTE still ~122m vs Lightning's 59m. Yaw-vs-CTE asymmetry says systematic bias remains. Did not have time to try dynamic single-track (slip-angle ST) or complementary filter with `a_lat_meas_mps2` — both flagged [unexplored] in the approach menu.
- `K1` (speed-dependent K_us) came out tiny on both platforms — borderline noise; could be dropped for parsimony.
- Tesla is V0 passthrough by design.

## Evaluation set

All Ford `data/sim/segments/FORD_*/**/sim.csv` (415 segments: 175 Lightning + 240 Mach-E). Dev cut = 110 routes (48 Lightning + 62 Mach-E) held out by route, never seen during fitting.
