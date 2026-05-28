---
title: webinar-AI runtime — operating contract
summary: Canonical contract for the sim-real correlation runtime sitting at the root of webinar-AI/. Holds the data layout, the operating mode (speed-known lateral-only), the runnable demos, the platform truth-channel matrix, and the units / signs / parameter conventions. M2+ of any AI-axis angle absorbs the relevant subset of this file into its own AGENTS.md.
updated: 2026-05-26
---

# webinar-AI — operating contract

Single-source-of-truth for the runtime that all webinar angles share. This file is **not** loaded automatically by any module — each angle's `modulo-N/AGENTS.md` absorbs the parts it needs into its own substrate, by hand, as it accretes.

## What this project is (and is not)

This is a sim-real correlation runtime around the **CommonRoad kinematic single-track (KS)** vehicle dynamics model. It runs the KS model on real openpilot rlog driving data and compares predicted lateral state (yaw rate `ψ̇`, lateral acceleration `a_y`) against the measured truth channels.

It is **not** a longitudinal-fidelity sandbox. Speed and steering angle are clamped to the measured values at every integration step.

## Operating mode — *speed-known lateral-only*

Real-data runs operate with `clamp_v_to_measured=True` and `clamp_delta_to_measured=True` in [`code/ks_model.py::simulate_ks`](code/ks_model.py).

Consequences:

- The KS state still has 5 components `(x, y, ψ, v, δ)` and the integrator still runs `dv/dt = a` and `dδ/dt = δ̇`, but their results are overwritten by the measured values each step.
- The model's **longitudinal channel is an input, not an output**. Reporting speed-state-vs-measured agreement is meaningless under this contract.
- The model's **lateral channel is what gets predicted**: `ψ̇` (`yaw_rate_pred_rads`), `a_y` (`a_y_pred_mps2`), heading, planar trajectory.
- The residual under test is the **lateral model lie**.

Do **not** "fix" lateral residuals by unclamping `v` or `δ` — the contract is the scope, not a bug.

## Platforms and truth-channel matrix

| Platform | Raw data | Sim CSV | Truth ψ̇? | Truth a_y? |
|---|---|---|---|---|
| `TESLA_MODEL_3` | 1025 segments / 1.785 GB | KS lateral prediction | **No** (IMU not decoded from party DBC) | **No** |
| `FORD_MUSTANG_MACH_E_MK1` | 315 segments / 0.817 GB | KS lateral prediction **+ truth** | Yes (`yaw_rate_meas_rads`) | Yes (`a_lat_meas_mps2`) |
| `FORD_F_150_LIGHTNING_MK1` | 230 segments / 0.597 GB | KS lateral prediction **+ truth** | Yes | Yes |

**Lateral-fidelity work must use Ford.** Tesla has no decodable yaw-rate truth today.

## Data layout

```
data/
  raw/segments/<PLATFORM>/<device>/<route>/<idx>/rlog.zst   ← downloaded by code/fetch_*.py
  sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv    ← produced by code/generate_simdata*.py
```

Today (`find data/sim -name '*.csv'`):

- Ford Mach-E: 2 segments
- Ford F-150 Lightning: 2 segments
- Tesla Model 3: 6 segments

Each Ford `sim.csv` has 18 columns:

```
t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2,
a_lat_meas_mps2, yaw_rate_meas_rads,         ← TRUTH (Ford only)
accel_pedal_pct, brake_pressed,
x_m, y_m, psi_rad, v_state_mps, delta_state_rad,
yaw_rate_pred_rads, a_y_pred_mps2,           ← PREDICTION
yaw_rate_resid_rads, a_y_resid_mps2          ← (pred − meas), already computed
```

`yaw_rate_resid_rads = yaw_rate_pred_rads - yaw_rate_meas_rads`. The lateral fidelity gap is in those two `*_resid_*` columns.

## Units and conventions

- All SI. Speeds in m/s, angles in rad, accelerations in m/s², yaw rates in rad/s.
- `delta_wheel_deg` is the steering-**wheel** angle in degrees (the column is a convenience copy of the raw CAN signal). `delta_road_rad` is the road-**wheel** angle in radians — that is what the KS model consumes. Conversion is `delta_road_rad = -deg2rad(delta_wheel_deg) / i_s` with `i_s` from `parameters.py`.
- Sign convention: `δ > 0` and `ψ̇ > 0` correspond to a **left turn** (CCW about +z, right-handed frame).
- Time grid in the CSV is uniform at 50 Hz (`dt = 0.02 s`).
- `psi_rad` from the KS integrator is heading, not yaw rate.

## Vehicle parameters

[`code/parameters.py`](code/parameters.py) — every value is **openpilot-canonical**, decoded from the rlog `carParams` event. Use `PARAM_BY_PLATFORM[platform_str]` to look up. KS rung needs `L, delta_max, delta_dot_max, a_min, a_max`; ST rung adds `m, I_z, l_f, l_r, C_alpha_f, C_alpha_r, i_s`.

The ST cornering stiffnesses (`C_alpha_f`, `C_alpha_r`) are the *prior* — they are what comma.ai ships in production today, decoded from the rlog. They are not the workshop's final calibration target.

## How to run things

```bash
source .venv/bin/activate
python code/run_ks_synthetic.py                       # no rlog needed
python code/generate_simdata.py                       # Tesla rlog → KS → data/sim/
python code/generate_simdata_ford.py                  # both Fords
python code/generate_simdata_ford.py FORD_MUSTANG_MACH_E_MK1
python code/plot_simdata_ford.py                      # PNGs alongside CSVs
```

End-to-end pipeline per Ford segment:

1. `code/rlog_reader.py` decodes the capnp rlog.
2. `code/adapter_ford_rlog.py` decodes Ford CAN via `opendbc/ford_lincoln_base_pt`. Surfaces `delta_meas, v_meas, a_long`, and the **truth channels** `yaw_rate_meas, a_lat_meas`.
3. `code/generate_simdata_ford.py` builds the `KSDriverInputs`, runs `simulate_ks(..., clamp_v_to_measured=True, clamp_delta_to_measured=True)`, writes the 18-column CSV.

## Known traps (the ratchet)

Every line below was engineered into this contract because some past run failed without it.

1. **Tesla has no truth channel.** If a script needs measured `ψ̇`, the platform must be Ford. Do not silently fall back to Tesla.
2. **Do not unclamp `v` or `δ` to "improve" lateral fidelity.** That breaks the speed-known contract; speed-state agreement is zero by construction and is not the metric.
3. **Steering-wheel deg vs road-wheel rad** are both in the CSV. Wrong column → factor-of-15 error (`i_s ≈ 15` on Mach-E). The KS state uses `delta_road_rad`.
4. **Sign convention is left-positive** for both `δ` and `ψ̇`. If `corr(δ, ψ̇)` comes out negative, you have a sign error somewhere.
5. **Parameters live in `PARAM_BY_PLATFORM`.** Do not hand-write `L = 2.875` or `m = 2035`. Look it up.
6. **KS has no slip.** `ψ̇` is computed as `(v / L) · tan(δ)` — no tyre, no slip angle, no force balance. Most of the lateral residual at high lateral acceleration is *expected* and is what an ST upgrade would close.

## Sister documentation

- `../KB002/workshop-sim-real/` — design and research home (not part of the runtime, not loaded by any module).
- `../KB002/workshop-sim-real/simulation-tools/commonroad/models.md` — the canonical doc on KS vs ST and on the speed-known framing.
