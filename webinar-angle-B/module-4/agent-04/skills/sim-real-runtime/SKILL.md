---
name: sim-real-runtime
description: Operating contract, platform truth-channel matrix, CSV schema, and vehicle parameters for the sim-real correlation runtime around the CommonRoad kinematic single-track (KS) model. Load this body whenever you need to know which channels are clamped vs predicted, which platforms have measured truth, what each `sim.csv` column means, or which numerical parameter value to use.
when-to-load: When the task touches `data/sim/`, `code/ks_model.py`, the `*_pred_*` / `*_meas_*` channels, or vehicle parameters.
inputs: Path to a Ford `sim.csv` if computing residuals.
outputs: Knowledge — you'll write residual-analysis or model-improvement code yourself; this skill is read-only context.
load-cost: ~250 tokens metadata, ~1200 tokens body.
---

# sim-real-runtime

## Operating contract — *speed-known, lateral-only*

Real-data runs operate with `clamp_v_to_measured=True` and `clamp_delta_to_measured=True` in `code/ks_model.py::simulate_ks`. Consequences:

- `v` and `δ` are **inputs**, not outputs. The integrator's own state updates are overwritten by measurement each step.
- The **predicted** channels are `yaw_rate_pred_rads` and `a_y_pred_mps2`.
- The **measured truth** channels (Ford only) are `yaw_rate_meas_rads` and `a_lat_meas_mps2`.
- The residual under test is lateral-only: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (pre-computed in the CSV).
- Speed-state agreement is zero by construction and is **not** the metric.

Do not unclamp `v` or `δ` — the contract is the scope, not a bug.

## Platforms and truth-channel matrix

| Platform                    | Sim CSV has truth `ψ̇`?     | Sim CSV has truth `a_y`?  | Use for lateral fidelity? |
|-----------------------------|:--------------------------:|:-------------------------:|:--:|
| `TESLA_MODEL_3`             | **No** (IMU not decoded)   | **No**                    | **No** |
| `FORD_MUSTANG_MACH_E_MK1`   | Yes (`yaw_rate_meas_rads`) | Yes (`a_lat_meas_mps2`)   | Yes |
| `FORD_F_150_LIGHTNING_MK1`  | Yes                        | Yes                       | Yes |

**Lateral-fidelity scoring must use a Ford platform.** Defaulting to Tesla because it has more segments and scoring self-consistency is a documented failure mode on past runs.

## Data layout

```
data/raw/segments/<PLATFORM>/<device>/<route>/<idx>/rlog.zst
data/sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv
```

Sim CSVs already exist — you do not need to regenerate.

## Ford `sim.csv` columns (18, at 50 Hz, `dt = 0.02 s`)

```
t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2,
a_lat_meas_mps2, yaw_rate_meas_rads,         ← TRUTH (Ford only)
accel_pedal_pct, brake_pressed,
x_m, y_m, psi_rad, v_state_mps, delta_state_rad,
yaw_rate_pred_rads, a_y_pred_mps2,           ← PREDICTION
yaw_rate_resid_rads, a_y_resid_mps2          ← (pred − meas), pre-computed
```

## Vehicle parameters — `code/parameters.py::PARAM_BY_PLATFORM`

Each entry is openpilot-canonical, decoded from the platform's rlog `carParams` event. Use the dict — do not hand-write values.

- **Mach-E MK1**: `L=2.984, m=2336, I_z=4879.05, l_f=1.313, l_r=1.671, C_αf=286 551, C_αr=355 912, i_s=17.0`.
- **F-150 Lightning MK1**: `L=3.683, m=2870, I_z=8108, l_f=1.510, l_r=2.173, C_αf=304 250, C_αr=349 807, i_s=18.0`.

ST cornering stiffnesses are openpilot's *prior*; they are not necessarily the right calibration for these tyres on these roads.

## Known traps

1. Tesla has no truth channel — must use Ford for lateral fidelity.
2. Do not unclamp `v` or `δ`.
3. `delta_wheel_deg` (degrees, CAN copy) vs `delta_road_rad` (radians, what KS consumes). Wrong column → factor-of-~15 error.
4. Sign convention is left-positive. Negative `corr(δ_road, ψ̇_meas)` on cornering = sign error.
5. Parameters in `PARAM_BY_PLATFORM` — look them up.
6. KS has no slip. Residual at high `|a_y|` is expected, not a bug.
7. V0 = `yaw_rate_resid_rads` as-is, no preprocessing. Any preprocessing belongs in V1+.
8. Same segment set + same regime mask across every variant row.
