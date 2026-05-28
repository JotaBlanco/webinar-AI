---
name: vehicle-dynamics-rlog
description: Vehicle-dynamics conventions used across the project — ISO 8855 sign convention, SI units, the KS → ST → non-linear-tyre fidelity ladder, naming conventions, time-grid resampling, and the heuristics the team uses when choosing a model variant. Load this body when you need to verify a sign, name a unit, decide which fidelity rung to climb to next, or write a variant table that will be reviewed by a vehicle dynamics engineer.
when-to-load: Before writing any sign-convention-sensitive code; before proposing a model upgrade (KS → ST or beyond); before computing a residual; before writing the variant ladder in REPORT.md.
inputs: None (read-only context).
outputs: Knowledge.
load-cost: ~250 tokens metadata, ~1000 tokens body.
---

# vehicle-dynamics-rlog

## Coordinate frames and sign conventions (ISO 8855)

- Body frame: X forward, Y **left**, Z **up**. ISO 8855 throughout — **not** SAE J670 (which has Y right and Z down). Aerospace NED conventions sometimes seen in autonomous-driving code; convert to ISO 8855 before applying any model.
- Yaw angle ψ: positive **counterclockwise viewed from above**. Yaw rate ψ̇ = dψ/dt. A **left turn produces positive ψ̇**.
- Steering wheel angle: positive CCW as seen by the driver, which produces a positive ψ̇. Some manufacturers' CAN signals invert this — a sign flip may be needed at the adapter layer.
- Lateral acceleration a_y: positive to the left. In a steady-state left turn, a_y is positive and points to the centre of the turn.

## Steering: wheel vs road

- `delta_wheel_deg` = steering-wheel angle, degrees, CAN-signal copy.
- `delta_road_rad` = road-wheel angle, radians, what the KS model consumes.
- Conversion: `delta_road_rad = -deg2rad(delta_wheel_deg) / i_s`. The leading minus is intentional; `i_s` is positive.
- Wrong column → factor-of-~15 error. `i_s ≈ 15-18` for the Mach-E and Lightning.

## Units (SI everywhere)

Angles in radians, speeds in m/s, accelerations in m/s², distances in m, mass in kg, moment of inertia in kg·m², cornering stiffness in N/rad, time in seconds. Exception: `delta_wheel_deg` in degrees (CAN convention).

## Sign sanity check

`corr(delta_road_rad, yaw_rate_meas_rads)` on cornering samples must be **positive**. If it's negative, you have a sign error somewhere upstream.

## Fidelity ladder (the team's standard variant order)

From cheapest to most complex:

1. **Point-mass** — no body, no tyres. Not used here.
2. **Kinematic single-track (KS)** — `ψ̇ = (v / L) · tan(δ)`. No slip. Currently in `code/ks_model.py`. This is the V0 baseline.
3. **Linear single-track (ST), prior C_α** — steady-state gain `ψ̇ = v·δ / (L·(1 + K_us·v²))` with `K_us = m·(l_r·C_αr − l_f·C_αf) / (L²·C_αf·C_αr)`. Use `PARAM_BY_PLATFORM` priors. At low `v → 0`, ST eigenvalues `~(C_αf+C_αr)/(m·v)` blow up — sub-step or fall back to KS below `v_min ≈ 2 m/s`.
4. **Linear ST, fit C_α** — re-fit cornering stiffnesses to data; bound to physical range (50–500 kN/rad). Pegging at the upper bound is a regression flag (the linear-ST form is wrong, not just the priors).
5. **Non-linear tyre (Pacejka)** — out of scope for an in-residual quick fix.
6. **ML residual learner** — Ridge/MLP on `[v, |a_y|, |δ|, sign(δ̇)]` against V_{n-1} residuals; **leave-one-segment-out CV only**. In-fold scoring is dishonest.

## Workshop discipline for the variant ladder

- Fixed order. Add **one** degree of freedom per rung. Attribute marginal RMSE drop per rung.
- Same segment set + same regime mask across every rung.
- Regimes: straight (`|δ_road| < 0.01`), steady cornering (`|δ_road| ≥ 0.01 ∧ |dδ/dt| < 0.05 rad/s`), transient cornering (`|δ_road| ≥ 0.01 ∧ |dδ/dt| ≥ 0.05`).
- Marginal drops sum to within 15% of total V0 → V_last drop; >15% means double-counting or instability.
- A regression rung (RMSE went up) must be reported with a physical reason.

## What to consider before climbing

- KS has no slip; the high-`|a_y|` residual is what an ST upgrade *could* close. Whether it *does* close it depends on whether the prior `C_α` matches the actual tyres.
- A per-segment bias on straight-line samples often soaks up an IMU yaw-gyro offset that ST cannot — try it first (often as part of V1).
- A residual learner can launder the gap *but only honestly if* its cross-validation is LOSO and the in-fold variant is reported as the baseline, not the scored result.
