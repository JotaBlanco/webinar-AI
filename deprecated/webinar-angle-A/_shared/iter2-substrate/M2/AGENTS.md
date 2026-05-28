# AGENTS.md — webinar-angle-A / module-2 (ratchet)

## Project purpose

Sim-real correlation runtime around the CommonRoad **kinematic single-track (KS)** vehicle dynamics model. KS is integrated over real openpilot rlog driving data; the lateral state it predicts (yaw rate `ψ̇`, lateral acceleration `a_y`) is compared against measured truth channels from the same rlog. **The model's lateral fidelity is what is under test.**

This is **not** a longitudinal-fidelity sandbox.

## Build / run

- `python3` is on PATH with `pandas`, `numpy`, `scipy`, `matplotlib` already installed. Use `python3`, never `python`. No venv to source.
- KS implementation: [`code/ks_model.py`](code/ks_model.py) — function `simulate_ks(...)`.
- Sim-CSV producers: [`code/generate_simdata.py`](code/generate_simdata.py) (Tesla), [`code/generate_simdata_ford.py`](code/generate_simdata_ford.py) (both Ford platforms). Already-produced CSVs live under `data/sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv`.

## Operating contract — *speed-known, lateral-only*

Real-data runs are produced with `clamp_v_to_measured=True` and `clamp_delta_to_measured=True` in [`code/ks_model.py`](code/ks_model.py). Consequences:

- Speed `v` and steering `δ` are **inputs**, not outputs. The integrator's own `v`/`δ` updates are overwritten by the measurement at every step.
- The **predicted** channels are `yaw_rate_pred_rads` and `a_y_pred_mps2`.
- The **measured truth** channels (Ford only) are `yaw_rate_meas_rads` and `a_lat_meas_mps2`.
- The residual under test is lateral-only: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (already pre-computed in the CSV).
- Speed-state agreement is zero by construction and is **not** the metric.

Do **not** "fix" lateral residuals by unclamping `v` or `δ` — that violates the contract.

## Platforms and truth-channel matrix

| Platform                       | Sim CSV has truth `ψ̇`?    | Sim CSV has truth `a_y`?  | Use for lateral fidelity? |
|--------------------------------|:-------------------------:|:-------------------------:|:--:|
| `TESLA_MODEL_3`                | **No** (IMU not decoded)  | **No**                    | **No** |
| `FORD_MUSTANG_MACH_E_MK1`      | Yes (`yaw_rate_meas_rads`)| Yes (`a_lat_meas_mps2`)   | Yes |
| `FORD_F_150_LIGHTNING_MK1`     | Yes                       | Yes                       | Yes |

**Lateral-fidelity scoring must use a Ford platform.** Defaulting to Tesla (more segments) and scoring self-consistency (model vs its own state) is a known failure mode.

## Data layout

```
data/
  raw/segments/<PLATFORM>/<device>/<route>/<idx>/rlog.zst
  sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv
```

Each Ford `sim.csv` has 18 columns:

```
t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2,
a_lat_meas_mps2, yaw_rate_meas_rads,         ← TRUTH (Ford only)
accel_pedal_pct, brake_pressed,
x_m, y_m, psi_rad, v_state_mps, delta_state_rad,
yaw_rate_pred_rads, a_y_pred_mps2,           ← PREDICTION (KS)
yaw_rate_resid_rads, a_y_resid_mps2          ← (pred − meas), pre-computed
```

## Units and sign conventions

- SI everywhere. Speeds in m/s, angles in rad, accelerations in m/s², yaw rates in rad/s.
- `delta_wheel_deg` is the steering-**wheel** angle in degrees (CAN-signal copy). `delta_road_rad` is the road-**wheel** angle in radians — that is what the KS model consumes. Conversion: `delta_road_rad = -deg2rad(delta_wheel_deg) / i_s` with `i_s` from [`code/parameters.py`](code/parameters.py).
- Sign convention: `δ > 0` and `ψ̇ > 0` correspond to a **left turn** (CCW about +z, right-handed frame).
- Time grid in the CSV is uniform at 50 Hz (`dt = 0.02 s`).

## Vehicle parameters

[`code/parameters.py`](code/parameters.py) — every value is openpilot-canonical, decoded from each platform's rlog `carParams` event. Use `PARAM_BY_PLATFORM[platform_str]` — **never** hand-write `L = 2.875` or `m = 2035`.

- KS needs: `L, delta_max, delta_dot_max, a_min, a_max`.
- Linear single-track (ST) — if you upgrade — needs additionally: `m, I_z, l_f, l_r, C_alpha_f, C_alpha_r, i_s`. The ST cornering stiffnesses are openpilot's *prior*; not necessarily the right calibration for these tyres.

## Baseline methodology — fixed, not a choice

Compute the baseline (V0) RMSE from the existing `yaw_rate_resid_rads` column **as-is**, with no preprocessing. Any preprocessing (per-segment bias removal, low-pass, outlier rejection, …) belongs **inside V1+**, not V0. Folding a fix into V0 hides the upgrade that earns it.

## Known traps (each line costs one past run)

1. **Tesla has no truth channel.** Lateral fidelity work must use Ford.
2. **Do not unclamp `v` or `δ`** — speed-state agreement is zero by construction and is not the metric.
3. **Wheel-deg vs road-rad.** Both columns are in the CSV. Wrong column → factor-of-~15 error (`i_s ≈ 15` on Mach-E).
4. **Sign convention is left-positive** for both `δ` and `ψ̇`. If `corr(δ, ψ̇)` comes out negative, you have a sign error somewhere.
5. **Parameters live in `PARAM_BY_PLATFORM`** — look them up.
6. **KS has no slip.** `ψ̇_KS = (v / L) · tan(δ)` — no tyre, no slip angle, no force balance. Most of the residual at high `|a_y|` is *expected* and is what an ST upgrade would close.
7. **Single markdown table in `REPORT.md`.** Any matchers downstream may latch onto the first markdown table; keep your variant ladder as the *only* markdown table in the report and use bullet lists elsewhere.

## What your `REPORT.md` must contain

- A clear statement of which platform you scored on and that its `*_meas_*` columns are measured truth (not predictions, not self-consistency).
- An explicit statement of what is **clamped** vs **predicted** under the speed-known contract.
- A variant ladder (V0 = baseline, V1, V2, …) with the *same* segment-set and the *same* regime-mask across every row.
- Per-variant RMSE on `yaw_rate_resid_rads`, broken out by regime: **straight / cornering steady / cornering transient**.
- An attribution column with each variant's **marginal** RMSE drop. Marginal drops should sum to approximately the total drop. Name the accounting scheme.
- Any variant that worsened the metric reported as a **regression** with a physical cause.
