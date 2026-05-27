# webinar-AI runtime — sim-real correlation

## Project purpose

Sim-real correlation runtime around the **CommonRoad kinematic single-track (KS)** vehicle dynamics model. We run the KS model on real openpilot rlog driving data and compare predicted lateral state (yaw rate `ψ̇`, lateral acceleration `a_y`) against measured truth channels. This project is **not** a longitudinal-fidelity sandbox.

## Operating mode — *speed-known lateral-only*

Real-data runs use `clamp_v_to_measured=True` and `clamp_delta_to_measured=True` in [`code/ks_model.py::simulate_ks`](code/ks_model.py). Consequences:

- The longitudinal channel is an **input**, not an output. Speed-state-vs-measured agreement is zero by construction; it is not a fidelity metric.
- The model predicts only the **lateral channel** (`ψ̇`, `a_y`, heading, planar position).
- The residual under test is the **lateral model lie**.

Do not "fix" lateral residuals by unclamping `v` or `δ` — that breaks the contract, it is not a bug.

## Build / run

```bash
# system python3 has pandas/numpy/scipy/matplotlib pre-installed; no venv needed
python3 code/run_ks_synthetic.py                              # no rlog needed
python3 code/generate_simdata.py                              # Tesla
python3 code/generate_simdata_ford.py                         # both Fords
python3 code/generate_simdata_ford.py FORD_MUSTANG_MACH_E_MK1 # one platform
python code/plot_simdata_ford.py                             # PNGs alongside CSVs
```

## Platforms and truth channels

| Platform | Raw segments | Truth ψ̇? | Truth a_y? |
|---|---|---|---|
| `TESLA_MODEL_3` | 6 sim CSVs available | **No** (IMU not decoded from party DBC) | **No** |
| `FORD_MUSTANG_MACH_E_MK1` | 2 sim CSVs available | Yes (`yaw_rate_meas_rads`) | Yes (`a_lat_meas_mps2`) |
| `FORD_F_150_LIGHTNING_MK1` | 2 sim CSVs available | Yes | Yes |

**Lateral-fidelity work must use Ford.** Tesla has no decodable yaw-rate truth.

## Data layout

```
data/
  raw/segments/<PLATFORM>/<device>/<route>/<idx>/rlog.zst   ← downloaded by code/fetch_*.py
  sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv    ← produced by code/generate_simdata*.py
```

Each Ford `sim.csv` has 18 columns at uniform 50 Hz (`dt = 0.02 s`):

```
t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2,
a_lat_meas_mps2, yaw_rate_meas_rads,         ← TRUTH (Ford only)
accel_pedal_pct, brake_pressed,
x_m, y_m, psi_rad, v_state_mps, delta_state_rad,
yaw_rate_pred_rads, a_y_pred_mps2,           ← PREDICTION
yaw_rate_resid_rads, a_y_resid_mps2          ← (pred − meas), already computed
```

`yaw_rate_resid_rads = yaw_rate_pred_rads - yaw_rate_meas_rads`. The lateral fidelity gap is in those `*_resid_*` columns.

## Units and sign conventions

- All SI. Speeds in m/s, angles in rad, accelerations in m/s², yaw rates in rad/s.
- `delta_wheel_deg` is the steering-**wheel** angle in degrees. `delta_road_rad` is the road-**wheel** angle in radians — that is what KS consumes. Conversion: `delta_road_rad = -deg2rad(delta_wheel_deg) / i_s` with `i_s` from `parameters.py`.
- **Sign convention: `δ > 0` and `ψ̇ > 0` correspond to a left turn** (CCW about +z).
- Time grid uniform at 50 Hz. `psi_rad` is heading, not yaw rate.

## Vehicle parameters

[`code/parameters.py`](code/parameters.py) — every value is **openpilot-canonical** (decoded from the rlog `carParams` event). Use `PARAM_BY_PLATFORM[platform_str]` to look up. Do not hand-write `L = 2.875` or `m = 2035` — look it up.

- KS rung needs: `L, delta_max, delta_dot_max, a_min, a_max`.
- ST rung adds: `m, I_z, l_f, l_r, C_alpha_f, C_alpha_r, i_s`.

ST cornering stiffnesses are the *prior* (what comma.ai ships); they are not a calibration ground truth.

## Skills inventory

The agent should inspect a skill's metadata before deciding to load its body. Never load all skill bodies eagerly. See [`skills/`](skills/).

- `lateral-fidelity-triage/` — procedure for measuring and *attributing* the lateral residual between KS-predicted `ψ̇` and measured `ψ̇` on Ford segments. Load when the task asks for lateral RMSE, residual decomposition, or contribution of model upgrades. Reads `references/ks-vs-st.md` for the catalogue of legitimate upgrades.

## References

Domain docs loaded on demand by skills, not eagerly:

- [`references/ks-vs-st.md`](references/ks-vs-st.md) — catalogue of physical lies in the KS model and what each upgrade rung (parameter recalibration, KS→ST, `C_α` tuning, residual ML) plugs. Read by the `lateral-fidelity-triage` skill.

## Known traps

Every line below was engineered in because some past run failed without it.

1. **Tesla has no truth channel.** If a script needs measured `ψ̇`, the platform must be Ford. Do not silently fall back to Tesla.
2. **Do not unclamp `v` or `δ` to "improve" lateral fidelity.** The speed-known contract is the scope, not a bug.
3. **Steering-wheel deg vs road-wheel rad** — both columns are in the CSV. Wrong column → factor-of-~15 error (`i_s ≈ 15` on Mach-E). KS consumes `delta_road_rad`.
4. **Sign convention is left-positive** for both `δ` and `ψ̇`. If `corr(δ, ψ̇)` comes out negative, you have a sign error somewhere.
5. **Parameters live in `PARAM_BY_PLATFORM`.** Do not hand-write magic numbers.
6. **KS has no slip.** `ψ̇` is computed as `(v / L) · tan(δ)` — no tyre, no slip angle, no force balance. Most of the lateral residual at high `|a_y|` is *expected*; an ST upgrade is what closes it.

## End-to-end Ford pipeline (for reference)

1. `code/rlog_reader.py` decodes the capnp rlog.
2. `code/adapter_ford_rlog.py` decodes Ford CAN via `opendbc/ford_lincoln_base_pt`. Surfaces `delta_meas, v_meas, a_long`, and the **truth channels** `yaw_rate_meas, a_lat_meas`.
3. `code/generate_simdata_ford.py` builds `KSDriverInputs`, runs `simulate_ks(..., clamp_v_to_measured=True, clamp_delta_to_measured=True)`, writes the 18-column CSV.
