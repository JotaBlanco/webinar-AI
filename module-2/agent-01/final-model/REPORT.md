# Lateral-fidelity V2 — agent-01

## KPIs (own evaluation, all Ford segments under data/sim/segments)

|                            | Yaw RMSE (rad/s) | CTE RMSE (m) |
|---------------------------:|-----------------:|-------------:|
| V0 (KS baseline)           |          0.01479 |       151.99 |
| **V2 (this submission)**   |      **0.01113** |   **107.06** |

Per-platform:

| Platform                  |   V0 yaw |   V2 yaw |    V0 CTE |    V2 CTE |
|--------------------------:|---------:|---------:|----------:|----------:|
| FORD_F_150_LIGHTNING_MK1  |  0.01633 |  0.00582 |    157.51 |     64.45 |
| FORD_MUSTANG_MACH_E_MK1   |  0.01362 |  0.01368 |    148.00 |    128.84 |

Per-regime yaw RMSE (overall): straight 0.00945 → 0.00653, steady 0.02812 → 0.02085, transient 0.03825 → 0.03299.

Segment set: 415 Ford segments (175 F150 Lightning, 240 Mach-E). All segments were used for scoring; train/dev split (even/odd index on sorted sim.csv paths) was used only for coefficient fitting.

## Model

V2 = linear bicycle (Ackermann + understeer gradient) with steering-offset and first-order yaw-rate lag:

    y_ss[k] = v[k] · (delta[k] − delta0) / (L + K_us · v[k]²)
    y[k+1]  = y[k] + (dt/(tau+dt)) · (y_ss[k+1] − y[k])

Trajectory integrated with the same Euler / cumsum scheme the grader uses (`_shared/traj_metrics.integrate_trajectory`), so predicted (x, y) is consistent with the predicted yaw rate.

Coefficients fitted by Nelder-Mead on the deterministic train split, per platform; pooled per-sample SSE on v>3 m/s as the loss.

| Platform                  |     L  |       K_us | delta0 (rad) | tau (s) |
|--------------------------:|-------:|-----------:|-------------:|--------:|
| FORD_F_150_LIGHTNING_MK1  | 3.700  |  4.54e-03  |     +1.39e-3 |  0.060  |
| FORD_MUSTANG_MACH_E_MK1   | 2.984  |  8.61e-04  |     −2.45e-5 |  0.058  |
| TESLA_MODEL_3 (prior)     | 2.875  |  7.00e-04  |     0.0      |  0.080  |

Tesla has no truth channel in the data, so its coefficients are an uncalibrated literature-informed prior.

## What was tried

- **V1 — understeer + bias only.** Linearised in (K_us, delta0); OLS closed-form. Train-only: F150 yaw 0.0164 → 0.0068, Mach-E 0.0125 → 0.0124. Big F150 win, Mach-E flat.
- **V2 — V1 + first-order lag.** Joint Nelder-Mead fit. ~60 ms tire build-up time constant fitted on both Fords (consistent with cross-correlation lag of 3–5 samples at 50 Hz seen in train data). V2 is shipped.

## Skills used / modified / bypassed

- **score-model / score.py** — used as-is for scoring. Indispensable.
- **pre-flight-final-model / preflight.py** — used as-is. Confirms final bundle shape (8/9 pass, only REPORT.md missing because the sub-agent write guard blocks it).
- **load-segments, make-train-dev-split, compare-models, visualise-segment** — bypassed. Train/dev split is implicit (even/odd indices on sorted paths); loading and metrics done inline. Time-budgeted not to load each skill body.
- **_shared/traj_metrics.py** — read for integration scheme; I replicated the same Euler scheme inside `predict.py` to keep the bundle self-contained (no import of `_shared/` at grade time).

## Honesty notes

- Mach-E yaw RMSE shows a tiny regression on the full set (0.01362 → 0.01368). The signal-to-noise ratio at zero steering is bad on Mach-E (yaw std ≈ 0.011 rad/s at |delta|<0.005, v>5 — a noise floor any sample-level model cannot beat). V2 still wins Mach-E CTE by 13 % because the lag matches the *timing* of corner entry/exit, which is what trajectory integration rewards.
- Tesla numbers are uncalibrated. Tesla has no `yaw_rate_meas_rads` truth in this dataset so I could not validate them; the prior is just a placeholder so `platform_support` stays honest.

## What I'd want next

A stratified per-segment hold-out (speed × steering-magnitude bins), plus a fusion model that uses `a_lat_meas_mps2` to bound yaw-rate uncertainty (Kalman or a simple complementary filter). V2 ignores measured lateral accel entirely — that's the obvious next lever. And, of course, ground-truth yaw for Tesla.
