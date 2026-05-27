# Lateral-prediction improvements — KS model, Ford corpus (agent-07)

**Headline metric**: RMS yaw-rate residual (deg/s), aggregated across **545 Ford segments / 1,580,767 samples** at 50 Hz from both `FORD_MUSTANG_MACH_E_MK1` and `FORD_F_150_LIGHTNING_MK1`. (Tesla has no measured yaw-rate truth channel in the CSVs, so it's excluded.)

| Variant | RMS (deg/s) |
| --- | --- |
| **V0 baseline KS (as stored)** | **1.0336** |
| **V4 final (full ladder)** | **0.7401** |

→ **28.4 % reduction**. Holdout split (70/30 by segment, fits learned on train only): on the Mach-E test set V0→V3 is 0.660 → 0.393 deg/s (-40 %); on the F-150 test set 1.386 → 1.057 deg/s (-24 %). The per-platform gains and understeer coefficient generalise out of segment, so the improvement is not just overfitting.

## What I implemented

The KS lateral prediction is `psi_dot = (v / L) · tan(δ_road)` with `δ_road = δ_wheel / i_s`. My ladder layered one knob at a time on top of that:

- **V1 — per-segment steering-angle bias.** Fit one DC offset `b` per segment so that `(v/L)·tan(δ - b)` minimises RMS yaw residual. Closed-form linear LS via the `sec²(δ)·b` linearisation. P95 of `|b|` is 3.1° at the steering wheel — typical sensor zero-offset.
- **V2 — per-platform yaw-rate gain `k`.** Replace prediction with `k·(v/L)·tan(δ−b)`. Mach-E k = 1.073 (effective steering ratio 17.0 → 15.85); F-150 k = 0.872 (16.9 → 19.38). The fact that the two platforms move in opposite directions tells you the carParams `steerRatio` isn't the real-world effective number for either.
- **V3 — understeer gradient `K_us`.** Swap in the linear-bicycle yaw-rate gain: `psi_dot = v·δ_eff / (L + K_us·v²)`. Fit one `K_us` per platform on top of V2's effective angle. Both platforms come out near `K_us ≈ 0.0011` (characteristic speed ≈ 53 m/s ≈ 190 km/h) — modest, consistent neutral understeer.
- **V4 — per-platform steering-to-yaw lag.** Integer-sample search ±10 samples (±200 ms) at 50 Hz. Mach-E best at +1 sample (20 ms), F-150 at +2 samples (40 ms). Tiny win.

## Attribution (sequential waterfall scheme)

Each level's contribution = `RMS_prev − RMS_this`, expressed both in absolute deg/s and as % of the original baseline error. Order matters: I added knobs in roughly decreasing prior-expected impact.

| Step | RMS (deg/s) | Δ (deg/s) | % of baseline error closed |
| --- | ---: | ---: | ---: |
| V0 baseline KS | 1.0336 | — | — |
| V1 + per-seg δ-bias | 0.9075 | +0.1261 | **12.2 %** |
| V2 + per-platform `i_s` rescale | 0.7959 | +0.1116 | **10.8 %** |
| V3 + understeer `K_us` | 0.7433 | +0.0526 | **5.1 %** |
| V4 + per-platform yaw lag | 0.7401 | +0.0032 | **0.3 %** |
| **Total** | | **+0.2935** | **28.4 %** |

By construction the deltas sum to the total. Per-segment bias (V1) and per-platform steering-ratio correction (V2) are roughly equal in impact and together carry 23 of the 28 points; understeer adds another 5; lag is negligible.

## Surprises

- The CSV column `a_lat_meas_mps2` for two F-150 segments is broken (RMS > 100 m/s² — DBC scale or stale-CAN bug). It made the *a_y* residual unusable as a headline metric (combined RMS 7.1 m/s², dominated by those two segments). I switched the primary metric to *yaw rate*, which is clean.
- The two Ford platforms' best `k` go in opposite directions (1.073 vs 0.872) even though their `carParams` steering ratios are nearly identical (17.0 vs 16.9). One per-platform scalar is doing more work than the openpilot-canonical value.
- The V3 understeer coefficients are almost identical across the two very different vehicles (sedan-ish EV vs heavy EV pickup), `K_us ≈ 0.0011 s²/m` — suggesting the missing physics is the same "mild understeer below the limit" everywhere, not a vehicle-specific tyre issue.
- Time lag is essentially zero (1–2 samples). The KS model isn't suffering from steering→yaw transport delay at 50 Hz; the residual is dominated by gain/bias and (slightly) nonlinear yaw gain at speed.

## Limitations

- I evaluated only on the Ford corpus because Tesla CSVs lack a measured yaw-rate channel.
- V1 (per-segment bias) is fit on the same data it's evaluated on. In production you'd estimate `b` from the first ~30 s of each drive — the holdout-style check would be per-segment temporal split, not per-corpus segment split. I did do a 70/30 segment-level holdout for V2 and V3 (the per-platform fits), and both generalise.
- I didn't touch the integrator (RK4 at the input rate is fine here), and I didn't implement an actual ST (dynamic single-track) model with cornering stiffnesses — V3's `K_us` is the linear-bicycle steady-state approximation, which captures most of what ST would buy at the residual-RMS level.
- I assumed yaw-rate is the right primary metric. Path-error and heading-error would be better workshop metrics but require integrating over time (more numerically sensitive). The model's yaw rate `psi_dot` is the prediction; the upstream change in `K_us` would propagate to path predictions trivially.
- Outputs: `out/ladder_results.json`, `out/holdout_results.json`, scripts at `tools/baseline.py`, `tools/ladder.py`, `tools/holdout.py`.

No harness friction encountered (no Write blocks tripped).

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Yaw-rate-only metric chosen because two F-150 sim CSVs have broken a_lat decoding (>100 m/s^2 RMS); did not investigate the DBC bug, just routed around it."
```
