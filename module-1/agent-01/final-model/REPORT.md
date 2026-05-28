# agent-01 — lateral-fidelity submission

## TL;DR

Replaced the bare KS yaw-rate formula with a single-DOF understeer-gradient
model + first-order steering lag + small bias, fit per platform on 70% of the
shipped Ford sim segments and evaluated on the 30% held out.

| platform | KPI | V0 | ours | reduction |
|---|---|---|---|---|
| F-150 Lightning (51 files held out) | yaw RMSE [rad/s] | 0.01849 | 0.01225 | 33.7% |
| | CTE mean [m] | 74.51 | 30.03 | 60% |
| | CTE median [m] | 43.47 | 23.55 | 46% |
| Mach-E (71 files held out) | yaw RMSE [rad/s] | 0.01506 | 0.01018 | 32.4% |
| | CTE mean [m] | 78.40 | 62.98 | 20% |
| | CTE median [m] | 31.84 | 27.70 | 13% |

## Model

    tau * d(delta_eff)/dt = (alpha * delta_road + beta) - delta_eff
    psi_dot               = v * delta_eff / (L + K_us * v^2)

Trajectory is midpoint-Euler integration of (psi, x, y) from psi_dot and
measured v_mps.

## Fitted parameters

| platform | alpha | K_us [s2/m] | tau [s] | beta [rad] |
|---|---|---|---|---|
| F-150 Lightning | 0.9671 | 0.00367 | 0.078 | -0.00115 |
| Mustang Mach-E  | 1.1784 | 0.00248 | 0.083 | +2e-5    |

Notable: alpha=1.18 on the Mach-E implies the openpilot steering ratio
(17.0) is too compliant; effective rack ratio ~ 14.4. F-150 alpha=0.97 is
barely off canonical. Both vehicles fit a steering lag of ~80 ms.

## Ladder

- V0 — shipped KS baseline (tan(delta) * v / L).
- V1 — add K_us. F-150 0.0144 -> 0.0077; Mach-E barely moves.
- V2 — add alpha (effective steering-ratio scale). Mach-E 0.0166 -> 0.0110.
- V3 — add beta (steering offset). F-150 0.0076 -> 0.0061.
- V4 (shipped) — add tau first-order lag. F-150 0.0061 -> 0.0052;
                 Mach-E 0.0110 -> 0.0104.

## predict()

predict(sim_df, platform) -> DataFrame aligned with sim_df.index, columns
yaw_rate_pred_rads, x_m, y_m. Required inputs: t_s, v_mps, delta_road_rad.
Robust to NaN via ffill/bfill.

## Limitations

- Tesla unsupported. No yaw_rate_meas_rads truth in the Tesla split, so I
  declined to ship a Tesla predictor rather than guess.
- Trajectory is open-loop midpoint Euler; any residual yaw bias drifts
  linearly in arclength. A bias-correction pass was tempting but felt
  out-of-spec.
- No tyre slip / no ST rung. Understeer + lag already buys >30% on yaw RMSE.
