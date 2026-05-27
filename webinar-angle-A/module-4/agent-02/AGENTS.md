# AGENTS.md — webinar-angle-A / module-4 (sensor + self-patch)

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

**Lateral-fidelity scoring must use a Ford platform.** Defaulting to Tesla (more segments) and scoring self-consistency is a known failure mode.

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
- `delta_wheel_deg` is the steering-**wheel** angle in degrees. `delta_road_rad` is the road-**wheel** angle in radians — that is what the KS model consumes. Conversion: `delta_road_rad = -deg2rad(delta_wheel_deg) / i_s` with `i_s` from [`code/parameters.py`](code/parameters.py).
- Sign convention: `δ > 0` and `ψ̇ > 0` correspond to a **left turn**.
- Time grid: 50 Hz (`dt = 0.02 s`).

## Vehicle parameters

[`code/parameters.py`](code/parameters.py) — openpilot-canonical values per platform. Use `PARAM_BY_PLATFORM[platform_str]`. Never hand-write `L = 2.875`.

- KS needs: `L, delta_max, delta_dot_max, a_min, a_max`.
- Linear ST needs additionally: `m, I_z, l_f, l_r, C_alpha_f, C_alpha_r, i_s`.

## Baseline methodology — fixed, not a choice

Compute V0 RMSE from the existing `yaw_rate_resid_rads` column **as-is**, with no preprocessing. Preprocessing belongs in V1+.

## Known traps (each line costs one past run)

1. **Tesla has no truth channel.** Lateral fidelity work must use Ford.
2. **Do not unclamp `v` or `δ`** — speed-state agreement is zero by construction and is not the metric.
3. **Wheel-deg vs road-rad.** Wrong column → factor-of-~15 error.
4. **Sign convention is left-positive.** Negative `corr(δ, ψ̇)` means a sign error.
5. **Parameters live in `PARAM_BY_PLATFORM`** — look them up.
6. **KS has no slip.** High-`|a_y|` residual is expected and is what ST would close.
7. **Single markdown table in `REPORT.md`.** Variant ladder is the *only* markdown table; everything else is bullet lists or paragraphs. The eval matcher latches onto the first markdown table.

## Skills inventory

- [`skills/lateral-fidelity-triage/SKILL.md`](skills/lateral-fidelity-triage/SKILL.md) — procedure for running the variant ladder with strict marginal-RMSE accounting. Imports [`skills/lateral-fidelity-triage/triage.py`](skills/lateral-fidelity-triage/triage.py).

## References

- [`references/ks-vs-st.md`](references/ks-vs-st.md) — bounded catalogue of legitimate variant upgrades, plus contract-violating ones to avoid.

## Evals

[`evals/lateral_fidelity_eval.py`](evals/lateral_fidelity_eval.py) is the computational sensor for `REPORT.md`. It scores six success metrics:

1. **truth-channel-correct** — report names the scored channel and identifies it as *measured*.
2. **contract-acknowledged** — report contains an explicit *clamped* + *predicted* statement.
3. **regime-breakdown-present** — variant table has per-regime columns (straight / steady / transient).
4. **methodology-consistent** — explicit statement that segment-set / regime-mask is held constant across rows.
5. **attribution-coherent** — `|Σ marginal drops − total drop| / total drop < 0.15`.
6. **honest-regression-flagged** — any variant that worsened the metric is reported as a regression with a physical reason (vacuously passes if no regression occurred).

Run with `python3 evals/lateral_fidelity_eval.py REPORT.md`. Exit 0 = all pass. Exit 1 = at least one fail.

**Self-patch loop.** If the eval fails, do **not** edit the eval. Edit [`skills/lateral-fidelity-triage/SKILL.md`](skills/lateral-fidelity-triage/SKILL.md) — add a "Ratchet R<N>" rule that prevents the failure recurring, regenerate the report following the new rule, re-run the eval. The skill is the artifact that grows; the eval is the judge.

## What your `REPORT.md` must contain

- Platform name and explicit statement that `yaw_rate_meas_rads` is *measured*.
- Explicit clamped-vs-predicted statement under the speed-known contract.
- Variant ladder (V0 baseline → V1, V2, …) — the **only** markdown table — with consistent segment-set + regime-mask.
- Per-variant RMSE on `yaw_rate_resid_rads`, broken out by regime.
- Marginal RMSE drop column. Accounting scheme named.
- Regressions flagged with physical cause.
