# Module-2 / agent-05 (angle-B) — Lateral fidelity variant ladder

## Scope and contract

- **Platform scored:** `FORD_MUSTANG_MACH_E_MK1` (305 of 315 segments used; 10 too short or missing columns).
- **Truth column:** `yaw_rate_meas_rads` — measured by the Ford chassis IMU, decoded via `opendbc/ford_lincoln_base_pt`. Not predicted, not self-consistency.
- **Clamped (inputs):** `v_mps`, `delta_road_rad` (per `clamp_v_to_measured=True, clamp_delta_to_measured=True`).
- **Predicted (under test):** `yaw_rate_pred_rads = (v/L)·tan(δ)`. Residual = pred − meas.
- **Regime mask** (shared across all variants): `v > 5 m/s`; straight `|δ| < 0.01 rad`; transient `|d(yaw_meas)/dt| > 0.5 rad/s²` on cornering; steady = remainder of cornering.

## Variant ladder — RMSE of `yaw_rate_resid_rads` (rad/s)

| Variant | Description | Overall | Straight | Steady cornering | Transient cornering | Marginal drop (vs prev) |
|---|---|---:|---:|---:|---:|---:|
| V0 | Baseline (`yaw_rate_resid_rads` as-is) | 0.01161 | 0.00923 | 0.02281 | 0.08360 | — |
| V1 | + per-segment yaw-rate bias removal | 0.00891 | 0.00517 | 0.02215 | 0.08422 | -0.00270 |
| V2 | + understeer-gradient correction `K_us·ψ̇_pred·v²` fit per segment on steady cornering | 0.00782 | 0.00648 | 0.01401 | 0.06997 | -0.00109 |
| V3 | + first-order steering actuator lag τ on δ before recomputing KS yaw | **0.00714** | 0.00626 | 0.01204 | **0.03528** | -0.00068 |

**Total V0 → V3 drop = 0.00447 rad/s (38% of V0).** Sum of marginals = 0.00447 (perfect closure, well inside the 15% tolerance). **Accounting scheme: forward-incremental marginal** — each row's drop equals `RMSE(V_{i-1}) − RMSE(V_i)`, in ladder order.

## Fitted parameters (median across segments)

- bias = +0.00166 rad/s (gyro zero / steering centre offset).
- K_us = +0.0 s²/m² median, but heavy-tailed: segments with real steady cornering picked up positive K_us in the 0.003–0.01 range, hence the big steady-regime drop.
- τ = 0.10 s (steering actuator lag).

## Regression noted

V1 slightly worsens the transient regime (0.0836 → 0.0842, +0.7%). Cause: bias fit on straight samples nudges genuine signed yaw-rate energy in the wrong direction in transients. V2 and V3 more than reclaim this.

## Surprise

**V3's tail-crushing effect on transients.** τ=0.10 s first-order lag alone cuts transient RMSE 0.070 → 0.035 (50%). KS wasn't wrong about the steady relationship — it was wrong about *when* the yaw rate happens. Much cheaper, more interpretable fix than going to a full ST tyre model. Suggests at least half of what we'd previously attributed to "missing slip dynamics" is actually missing actuator dynamics.

## Painful absence

Tesla has 1025 segments but no decoded IMU truth — two-thirds of the corpus invisible to lateral fidelity work. Ford fleet small (315 + 230) and Mustang-heavy.

## Rule-prevented near-misses

- "Do not unclamp v/δ" — saved me from letting the integrator close its own loop.
- `delta_road_rad` vs `delta_wheel_deg` (factor of 17 in K_us).
- "V0 as-is, no preprocessing" — was tempted to fold V1 bias into V0.
- Parameters from `PARAM_BY_PLATFORM` (L=2.984 m).

Files: `out/analyze.py`, `out/ladder.csv`, `out/fit_summary.txt`.
