# AGENTS.md — webinar-angle-B / module-2

You are working on a sim-real correlation project for a vehicle dynamics modelling team. This document is the single source of truth for everything you need to know about the project. Read it carefully — there is no skills inventory, no `references/`, no `evals/`, no separate domain documentation. Everything is here, in one place, and will be re-read in your context every turn.

## Project purpose and engineering culture

This project explores the comparison between simulated vehicle dynamics models and real driving data captured by openpilot (a comma.ai driving-data platform), with the goal of understanding how well classical physics-based vehicle dynamics models capture real-world driving behaviour and where they fall short. The work has applications in autonomous driving research, advanced driver-assistance systems (ADAS), motorsport analytics, vehicle development, calibration of digital twins, and broader sim-to-real correlation efforts across the automotive sector. The team includes vehicle dynamics engineers with motorsport backgrounds, data scientists with experience in residual learning and physics-plus-data hybrid modelling, and software engineers experienced in data infrastructure and streaming systems. Decisions in this project should always consider the production deployment perspective — i.e. models are not just for research but eventually need to run in real-time or near-real-time on vehicle compute or edge infrastructure. We tend to favour interpretable physics-based approaches over pure black-box machine learning, especially when the underlying domain has strong first-principles knowledge. The team has spent considerable time understanding the physics; the goal of this project is to use that understanding to improve the prediction, not to replace it with a learned function. When trade-offs arise between interpretability and accuracy, interpretability usually wins unless the accuracy gain is decisive and the production runtime cost is acceptable.

## Build, run, environment

The project is Python-based. `python3` is on PATH with `pandas`, `numpy`, `scipy`, `matplotlib` already installed. Use `python3`, never `python`. There is no virtual environment to activate. Dependencies that may or may not be installed include `cantools` and `pycapnp` (for CAN-bus and rlog decoding) and `zstandard` (for compressed log files). The team's main scripts are in `code/` (a symlink, read-only by contract). The data lives in `data/` (also a symlink, also read-only by contract). Any output you produce — scripts, intermediate CSVs, plots, the final `REPORT.md` — must go inside your own working directory, preferably under `out/` for results and `tools/` for scripts.

End-to-end pipeline per Ford segment, for context (you should not need to re-run any of this — the sim CSVs already exist):

1. `code/rlog_reader.py` decodes the capnp rlog using the pinned cereal schema in `code/_schema/`.
2. `code/adapter_ford_rlog.py` decodes Ford CAN signals via the openpilot DBC (`opendbc/ford_lincoln_base_pt`). This adapter surfaces `delta_meas, v_meas, a_long`, and — critically — the **measured truth channels** `yaw_rate_meas, a_lat_meas`.
3. `code/generate_simdata_ford.py` builds a `KSDriverInputs` object, runs `simulate_ks(..., clamp_v_to_measured=True, clamp_delta_to_measured=True)`, and writes the resulting 18-column CSV to `data/sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv`.

## Vehicle dynamics conventions (non-negotiable across the whole project)

This section captures the conventions the team uses across all vehicle dynamics work. These conventions are non-negotiable and apply to every model, every analysis, every plot, and every report.

### Coordinate frames and sign conventions

The vehicle body frame is defined with the X axis pointing forward (longitudinal, in the direction of travel when the steering is centred), the Y axis pointing to the *left* of the vehicle (lateral, positive towards the driver's left), and the Z axis pointing *up* (vertical, opposite to gravity). This is the **ISO 8855** convention and is the convention used across the automotive industry for vehicle dynamics work — note that it differs from the SAE J670 convention which has Y pointing right and Z pointing down. Aerospace conventions (e.g. NED — North-East-Down) are sometimes seen in autonomous driving codebases and should be avoided; if a tool uses NED, the data should be converted to ISO 8855 before any model is applied.

Heading (yaw angle, ψ) is measured *positive counterclockwise when viewed from above*, with zero pointing in the direction of the world X axis. Yaw rate (ψ̇, sometimes written `r` or `psi_dot`) is the time derivative of heading and is therefore also positive counterclockwise. A left turn produces a positive yaw rate; a right turn produces a negative yaw rate. The sign of the steering wheel angle should be consistent: a counterclockwise rotation of the steering wheel (as seen by the driver) is positive and produces a left turn — but be aware that some manufacturers' CAN signals invert this convention internally and a sign flip may be needed at the adapter layer.

Lateral acceleration (a_y, sometimes a_lat or Ay) follows the body frame Y axis convention: positive when accelerating to the left. For a vehicle in a steady-state left turn, the lateral acceleration is positive and points towards the centre of the turn (which is to the left of the vehicle). Centripetal acceleration in a body frame is therefore positive in a left turn and negative in a right turn — do not confuse this with the world-frame centripetal acceleration which always points from the vehicle towards the instantaneous centre of rotation.

Steering angle is typically reported in two forms: the steering wheel angle (the angle of the steering wheel as turned by the driver, in degrees) and the road wheel angle or "front wheel steer angle" (the actual angle of the front road wheels relative to the vehicle longitudinal axis, in radians for modelling). The steering ratio relates the two: road wheel angle = steering wheel angle / steering ratio. Steering ratios vary by vehicle and even by speed for vehicles with variable-ratio steering racks; typical passenger car values are between 12:1 (sporty) and 18:1 (luxury/SUV).

### Units

All quantities are expressed in SI units unless explicitly stated. The exceptions are: steering wheel angle (degrees, because it is the natural unit in which it is measured and reported by the CAN bus on most production vehicles); vehicle speed when reported in human-readable contexts (km/h is common in non-US datasets; mph in US datasets); tyre pressures (psi or bar depending on the team). For modelling: every angular quantity is in radians; every speed in m/s; every acceleration in m/s²; every distance in metres; every mass in kg; every moment of inertia in kg·m²; every cornering stiffness in N/rad; every time in seconds.

### Vehicle dynamics model fidelity ladder

The team works across a fidelity ladder of vehicle dynamics models. From lowest to highest fidelity:

1. **Point-mass model.** No body, no tyres, no slip. Used for very high-level trajectory planning where geometric feasibility is the only concern. Not relevant for this project.
2. **Kinematic single-track (KS) model.** The "driving-school" model. The car is a rigid rod of length L (the wheelbase) with a single front wheel and a single rear wheel. There is no tyre, no slip, no lateral force balance — wherever the front wheel points, the car follows. The KS model has 5 states: position (x, y), heading (ψ), longitudinal speed (v), and steering angle (δ). Yaw rate computes as `ψ̇ = (v / L) · tan(δ)`. This is the model currently in `code/ks_model.py`.
3. **Single-track dynamic model (ST).** Adds tyre cornering stiffness (linear regime), lateral force balance, and the slip angle. The car now resists lateral motion based on tyre cornering stiffness. The states are typically (x, y, ψ, v, δ, β, ψ̇) where β is the sideslip angle. Steady-state yaw-rate gain is `ψ̇ = v · δ / (L · (1 + K_us · v²))` with `K_us = m · (l_r · C_αr − l_f · C_αf) / (L² · C_αf · C_αr)`.
4. **Multi-body single-track with non-linear tyres.** Adds non-linear tyre behaviour (Pacejka magic formula or similar), tyre saturation, weight transfer, etc.
5. **Full multi-body vehicle dynamics simulation.** Out of scope for this project; would require commercial tools (CarSim, Adams Car, IPG CarMaker).

### Time alignment and sampling rates

CAN bus signals on production vehicles are sampled at varying rates depending on the message: typically 100 Hz for chassis dynamics signals (yaw rate, lateral acceleration, longitudinal acceleration, wheel speeds), 50 Hz for steering signals, and 10-20 Hz for slower signals. The IMU sensor on openpilot devices samples at 100 Hz. The GPS sample rate is typically 10 Hz. When comparing signals or feeding them into a model, all signals should be resampled to a common time grid; the team uses a 50 Hz grid (`dt = 0.02 s`) for sim-real comparisons.

### Naming conventions

Variables in code should use lowercase with underscores. Greek letters are spelled out (delta, psi, beta, omega) rather than encoded as unicode. Time series arrays are named with the underlying physical quantity followed by an underscore and the unit suffix where ambiguous (e.g. `delta_rad`, `v_mps`, `a_y_mps2`). The "_rads" suffix denotes radians per second (so `yaw_rate_rads` is in rad/s, not rad). Predicted-vs-measured pairs are suffixed `_pred` and `_meas` respectively. Residuals are computed as `pred − meas` by the team's convention (note: the residual sign in `yaw_rate_resid_rads` follows this convention; if you see references to "meas − pred" elsewhere they are using the opposite convention — clarify before using).

## Operating contract — *speed-known, lateral-only*

Real-data runs operate with `clamp_v_to_measured=True` and `clamp_delta_to_measured=True` in `code/ks_model.py::simulate_ks`. Consequences:

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

## Vehicle parameters

`code/parameters.py` — every value is **openpilot-canonical**, decoded from each platform's rlog `carParams` event. Use `PARAM_BY_PLATFORM[platform_str]` to look up. KS needs `L, delta_max, delta_dot_max, a_min, a_max`; ST adds `m, I_z, l_f, l_r, C_alpha_f, C_alpha_r, i_s`. The ST cornering stiffnesses (`C_alpha_f`, `C_alpha_r`) are the *prior* — what comma.ai ships in production today, decoded from the rlog. They are not necessarily the right calibration target for these particular tyres on these particular roads.

For the Ford Mustang Mach-E MK1 specifically: `L=2.984 m`, `m=2336 kg`, `I_z=4879.05 kg·m²`, `l_f=1.313 m`, `l_r=1.671 m`, `C_αf=286,551 N/rad`, `C_αr=355,912 N/rad`, `i_s=17.0`. For the Ford F-150 Lightning MK1: `L=3.683 m`, `m=2870 kg`, `I_z=8108 kg·m²`, `l_f=1.510 m`, `l_r=2.173 m`, `C_αf=304,250 N/rad`, `C_αr=349,807 N/rad`, `i_s=18.0`.

## Known traps (the engineering team's accumulated wisdom)

Every line below was engineered into this document because some past run failed without it. Read every one before starting.

1. **Tesla has no truth channel.** If a script needs measured `ψ̇`, the platform must be Ford. Do not silently fall back to Tesla.
2. **Do not unclamp `v` or `δ` to "improve" lateral fidelity.** That breaks the speed-known contract; speed-state agreement is zero by construction and is not the metric.
3. **Steering-wheel deg vs road-wheel rad** are both in the CSV. Wrong column → factor-of-15 error (`i_s ≈ 15-18` on Mach-E and Lightning). The KS state uses `delta_road_rad`.
4. **Sign convention is left-positive** for both `δ` and `ψ̇`. If `corr(δ, ψ̇)` comes out negative on cornering samples, you have a sign error somewhere.
5. **Parameters live in `PARAM_BY_PLATFORM`.** Do not hand-write `L = 2.875` or `m = 2035`. Look it up.
6. **KS has no slip.** `ψ̇` is computed as `(v / L) · tan(δ)` — no tyre, no slip angle, no force balance. Most of the lateral residual at high lateral acceleration is *expected* and is what an ST upgrade would close.
7. **Use Ford `sim.csv` only for lateral fidelity work.** The CSVs already exist in `data/sim/segments/`; you do not need to regenerate.
8. **All variants must use the same segment set and the same regime mask.** Otherwise the numbers across variants are not comparable.
9. **Baseline (V0) RMSE is computed from `yaw_rate_resid_rads` as-is, no preprocessing.** Any preprocessing (bias removal, low-pass, outlier rejection) belongs in V1+, not V0. Folding a preprocessing step into V0 hides the upgrade that earns it.
10. **Attribution should be marginal**, not isolated, unless you explicitly say otherwise. Sum of marginal RMSE drops should equal the total drop V0 → V_last to within ~15%.
11. **The sub-agent harness (your harness) blocks `Write` on files matching `(report|findings|summary|analysis).*\.md$`.** You cannot write `REPORT.md` directly. Return the final report content in your final text response; the orchestrator will persist it.

## What your `REPORT.md` must contain

- The platform you scored on, and an explicit statement that the truth column you compared against (`yaw_rate_meas_rads`) is **measured**, not predicted or self-consistency.
- An explicit statement of what is **clamped** vs **predicted** under the speed-known contract.
- A variant ladder (V0, V1, V2, …) with consistent segment-set and consistent regime mask across rows.
- Per-variant RMSE on `yaw_rate_resid_rads`, broken out by regime (straight / steady cornering / transient cornering).
- A marginal-drop column. Name the accounting scheme.
- Any variant that worsened the metric reported as a regression with a physical cause.
