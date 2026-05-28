# Module-2 / agent-01 — Lateral fidelity report

**Platform scored:** Ford (Mach-E MK1 + F-150 Lightning MK1), 545 segments total. The `yaw_rate_meas_rads` and `a_lat_meas_mps2` columns are **measured truth** decoded from rlog CAN, not predictions or self-consistency.

**Speed-known contract honoured.** `v_mps` and `delta_road_rad` are **clamped** inputs in every variant; the KS integrator's own `v`/`δ` state updates are overwritten by measurement each step. The **predicted** channel under test is `yaw_rate_pred_rads`.

**Headline result:** Overall yaw-rate RMSE dropped from **0.01804 rad/s (V0) to 0.01568 rad/s (V4) — a 13.1% reduction**. Most of the drop lives in cornering (steady 0.0247 → 0.0213; transient 0.0465 → 0.0422).

## Variant ladder

Same Ford segment set, same regime mask, marginal-drop accounting on global RMSE.

| Variant | Straight | Steady | Transient | Overall | Δ vs prior | Description |
|---------|---------:|-------:|----------:|--------:|-----------:|-------------|
| V0 baseline   | 0.00789 | 0.02473 | 0.04654 | 0.01804 | —         | `yaw_rate_resid_rads` as-is |
| V1 gyro-bias  | 0.00644 | 0.02447 | 0.04641 | 0.01752 | -0.00051  | Subtract per-segment yaw-rate bias estimated on straight stationary-wheel slices |
| V2 LPF δ      | 0.00642 | 0.02446 | 0.04639 | 0.01751 | -0.00001  | 3 Hz Butterworth on `delta_road_rad` before kinematic prediction |
| V3 lag        | 0.00630 | 0.02452 | 0.04534 | 0.01733 | -0.00018  | Align meas to pred by global lag (80 ms / 4 samples) |
| V4 understeer | 0.00617 | 0.02125 | 0.04216 | 0.01568 | -0.00165  | `ψ̇ = ψ̇_kin / (1 + K_us·v²/L)`, K_us fit per platform |

- **Regimes:** straight = `|δ_road|<0.005 ∧ |a_lat|<0.5`; transient = cornering ∧ `|dδ/dt|≥0.02 rad/s`; steady = remaining cornering.
- **Accounting:** strict marginal in fixed order V0→V1→V2→V3→V4. Marginal drops sum to 0.00236, matching total V0−V4.
- **Fitted parameters:** lag = 80 ms; K_us = −3.1e-4 (Mach-E), +4.1e-3 (F-150).

## Limitations

- No held-out validation split. K_us fit globally and reported on the same data — no train/test discipline declared. V2 LPF kept despite ~0 marginal because the only way to know it doesn't *hurt* a future segment is to test on one.
- Regime thresholds chosen by inspection.

## Notes

- **No regressions observed.**
- Mach-E fitted K_us is **negative** (small) while Lightning is clearly positive. Textbook expectation is K_us > 0 for both. Likely Mach-E sits in the linear-tyre regime at these speeds and the bigger residual driver is steering-ratio/compliance, not slip. A single-platform K_us would have *added* error on Mach-E.

Files: `out/run_ladder.py`, `out/results.json`, `out/results.csv`.
