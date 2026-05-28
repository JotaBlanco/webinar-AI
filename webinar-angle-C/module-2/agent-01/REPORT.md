# Module-2 / agent-01 (angle-C) — Lateral fidelity variant ladder

## Setup

- **Platform:** `FORD_MUSTANG_MACH_E_MK1` (315 segments, 913 626 samples @ 50 Hz). Tesla excluded — no decodable yaw-rate truth (rule 4).
- `yaw_rate_meas_rads` is the **measured** IMU yaw rate from the rlog; `yaw_rate_pred_rads` is KS-model output. Residuals follow team convention `pred − meas` (rule 1).
- **Operating contract (rule 5):** `v_mps` and `delta_road_rad` clamped to measured at every integrator step; only lateral states predicted.
- **Sign sanity:** `corr(δ_road, ψ̇_meas)` on cornering = **+0.701** → ISO-8855 holds (rule 2).
- **Train/test split:** every 5th sample → test, interleaved (rule 7). Test-set RMSEs reported.
- **Regime mask** (fixed): straight `|δ_road| < 0.5°`; transient (not straight ∧ 1-s rolling σ(δ_road) > 0.3°); else steady. Counts: straight 774k / steady 97k / transient 42k.
- **Accounting:** strict marginal V0→V4.

## Headline

**Yaw-rate RMSE 0.924 → 0.892 deg/s on test as a generalising per-platform fit (V2+V3), a 3.5% reduction. With per-segment calibration on top (V4) it falls to 0.792 deg/s (-14.3%), but that final hop is calibration, not model improvement (rule 8).**

## Variant ladder (yaw-rate RMSE, deg/s, test set)

| Variant | Fit scope | Overall | Δ vs prev | Straight | Steady | Transient |
|---|---|---|---|---|---|---|
| V0 baseline | n/a | 0.9244 | — | 0.4965 | 1.4251 | 3.0482 |
| V1 constant yaw bias | per-platform (1 scalar = +0.00075 rad/s) | 0.9248 | -0.0004 | 0.4945 | 1.4294 | 3.0524 |
| V2 steering-gain k | per-platform (k=1.0687, on top of V1) | 0.8927 | +0.0321 | 0.5336 | 1.3999 | 2.7406 |
| V3 lag align | per-platform (+1 sample = +20 ms) | 0.8895 | +0.0031 | 0.5322 | 1.4148 | 2.7058 |
| V4 per-segment bias | per-segment (315 scalars; calibration) | 0.7922 | +0.0973 | 0.3223 | 1.3809 | 2.6991 |

## a_y RMSE (m/s²) — re-derived per rule 9

| Variant | Overall | Straight | Steady | Transient |
|---|---|---|---|---|
| V0 | 0.338 | 0.311 | 0.491 | 0.379 |
| V1 | 0.335 | 0.307 | 0.491 | 0.379 |
| V2 | 0.363 | 0.331 | 0.557 | 0.349 |
| V3 | 0.363 | 0.331 | 0.558 | 0.354 |
| V4 | 0.345 | 0.309 | 0.549 | 0.357 |

## Per-variant interpretation

- **V0** unmodified residual. Errors dominated by transient cornering (3.05 deg/s).
- **V1 (≈ null)** Platform-level median residual is +0.00075 rad/s — dominated by 84% straight samples; both `pred` and `meas` near zero. No real lift.
- **V2 (per-platform steering gain k=1.069)** Fit by least squares on TRAIN. Big drop on transient (3.05 → 2.74, -10%); but **straight regresses** (0.50 → 0.53) — k>1 amplifies near-zero noise. The k>1 implies effective wheelbase is ~6% too large, or steering ratio is ~6% too low.
- **V3 (+20 ms lag)** Tiny but real on transients (2.74 → 2.71); steady regresses slightly. The optimal lag differs between regimes.
- **V4 (per-segment bias)** Biggest single jump, but **calibration, not model improvement** (rule 8). Straight-regime drop (0.53 → 0.32) is almost the entire effect: IMU mounting bias is a constant on straights.

## Regressions flagged

1. V2 hurts straight (0.497 → 0.534). Gain on near-zero predictor amplifies noise. Mitigation candidate: regime-conditional gain.
2. V2/V3 hurt `a_y` overall and in steady cornering (0.338 → 0.363). `a_y = v·ψ̇` coupling: scaling ψ̇ overshoots measured a_lat. The yaw and a_y channels disagree about which direction to scale — signature of structural KS limit (no slip angle).
3. V4 hurts a_y in steady (0.491 → 0.549) — same coupling.

## Painful absence

**Sub-agents / parallel evaluation.** Five variants × three regimes × two channels × cross-validation is embarrassingly parallel and I ran it serially. A sub-agent per variant with a shared scoring module would have surfaced V2's regime-conditional regression on straights an iteration earlier.

## Near-misses

- Rule 1 (`pred − meas`): had I assumed the inverse convention, I would have added the median bias and reported V1 as a win.
- Rule 7 (interleaved split): with a contiguous split V4's per-segment bias would have looked like a 0.2 deg/s lift because the same segment IDs would appear in train and test.
- Rule 8 (per-segment label): V4 is the biggest absolute drop; without the label I would have led with it.
- Rule 9 (re-derive a_y): catching the coupling exposed that V2/V3 regress a_y — a genuine finding.

## Surprise

V2's k=1.069 says the platform under-predicts yaw by ~7%. That's a wheelbase/steering-ratio mismatch in `PARAM_BY_PLATFORM` of the same scale — not noise, not slip — checkable against the openpilot `carParams` event. Yet V2 simultaneously worsens `a_y` in steady. The two truth channels disagree about how to scale, signature of a structural KS limit (no slip angle) rather than parameter error. Right next move isn't a third scalar, it's DST.

Files: `tools/`, `out/`.
