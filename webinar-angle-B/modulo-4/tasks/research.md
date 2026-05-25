# Phase 1 — Research

## 1. Substrate map

**Code tree (`code/`, symlinked).** The lateral pipeline is three files:
`adapter_ford_rlog.py` (CAN → resampled measurement struct at 50 Hz),
`ks_model.py` (KS dynamics, RK4 integrator, `simulate_ks(...)`), and
`generate_simdata_ford.py` (driver that ties them together, writes one CSV per
segment). Parameters are openpilot-canonical, read from rlog `carParams`
(`code/parameters.py` — `MachEKS/ST`, `F150LightningKS/ST`).

**Data tree (`data/`, symlinked).** Two Ford platforms, 2 segments each, all
~2898 rows at 50 Hz (~58 s):
- `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/{08ec7b9a..., 112bd787...}/.../sim.csv`
- `data/sim/segments/FORD_F_150_LIGHTNING_MK1/{0b2c0bec..., 112e4d6e...}/.../sim.csv`

**Operating contract.** `simulate_ks(..., clamp_v_to_measured=True,
clamp_delta_to_measured=True)`. Per `skills/sim-real-runtime`:
*"The model's longitudinal channel is an input, not an output... the lateral
channel — yaw rate, lateral acceleration, heading, planar trajectory — is what
gets predicted."* The model is `psi_dot = (v/L)*tan(delta)`, `a_y = v*psi_dot`.
Residuals `yaw_rate_resid_rads = meas - pred` and `a_y_resid_mps2 = meas - pred`
are pre-computed in the CSV. Saturation: `delta_dot` and `a` are clipped to
parameter limits inside `ks_dynamics`, but under clamps those rates are
overridden anyway.

## 2. Baseline measurement

Concatenating both segments per platform (5796 rows each), I computed:

| Platform | N | RMSE psi_dot (deg/s) | bias psi_dot (deg/s) | RMSE a_y (m/s^2) | bias a_y (m/s^2) | corr psi_dot | corr a_y |
|---|---|---|---|---|---|---|---|
| Mach-E | 5796 | **0.505** | +0.316 | **0.062** | -0.042 | 0.463 | 0.804 |
| F-150  | 5796 | **1.105** | -0.873 | **0.443** | -0.172 | 0.987 | 0.789 |

Per-segment context:
- **Mach-E** segments are *near-straight-line driving*: max |delta_road| = 0.14 / 0.31 deg,
  max |psi_dot_meas| ~ 1.25 deg/s, max |a_y_meas| = 0.38 m/s^2. The corr psi_dot = 0.46 is
  garbage because the model correctly predicts ~zero everywhere and almost all
  the RMS is **yaw-rate sensor bias / noise**. Segment-specific straight-line
  biases on psi_dot: seg1 **+0.700** deg/s, seg2 **-0.092** deg/s.
- **F-150** segments actually corner: |delta_wheel| up to 25 deg, |a_y_meas| up to
  2.9 m/s^2, corr psi_dot = 0.987. Median ratio `psi_dot_meas / psi_dot_pred` on turns
  (|psi_dot_meas|>2 deg/s) = **0.851** — KS over-predicts yaw rate by ~15%, the
  textbook tyre-compliance gap. Straight-line bias: seg1 **-1.49** deg/s,
  seg2 **-0.53** deg/s — also large and *segment-specific* (drift across drives).

Regime breakdown (F-150, RMSE deg/s):
- by speed: low (<5 m/s) 0.53; mid (10-20) 0.64-0.74; high (>=25) **1.37**
- by |a_y_meas|: <1 -> 1.05; 1-2 -> 1.42; 2-3 -> **2.16**
- Residual grows monotonically with both v and |a_y| -> consistent with tyre
  compliance + a per-segment psi_dot bias offset.

Files used:
- `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/08ec7b9afc6b766e/00000000--33439c2a9c/1/sim.csv`
- `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/112bd787ceca718d/00000003--55220ffbee/12/sim.csv`
- `data/sim/segments/FORD_F_150_LIGHTNING_MK1/0b2c0bec9a28eb0f/00000001--82c7a5f419/34/sim.csv`
- `data/sim/segments/FORD_F_150_LIGHTNING_MK1/112e4d6e0cad05e1/00000001--3975f8fbf5/9/sim.csv`

## 3. Hypothesis space

**H1. Per-segment yaw-rate sensor bias removal.** Signature: straight-line
mean psi_dot_resid clearly != 0 (+0.70 / -0.09 Mach-E; -1.49 / -0.53 F-150) and
varies between segments. Mechanism: yaw-rate sensor zero-offset drifts across
power cycles. Fix: estimate bias `b_hat` from samples where |delta_road|<thresh
AND |psi_dot_meas|<thresh AND v>some min, subtract from the measured channel
(or apply as a correction). Expected effect: large on Mach-E (removes ~entire
RMSE since model is correctly ~0), meaningful on F-150 (~0.5-1 deg/s of bias).
Cost: trivial (~20 LOC).

**H2. ST model with linear tyre cornering stiffness.** Signature: F-150 turn
gain meas/pred = 0.851; residual grows with |a_y| and v. Mechanism: KS
ignores lateral force balance -> over-predicts at speed because real tyres
develop slip angles. ST adds beta (sideslip), uses (m, I_z, l_f, l_r, C_af,
C_ar) — all present in `MachEST`/`F150LightningST` already. Expected: cuts
the ~15% high-G gain error -> could drop F-150 RMSE by 30-50% at high |a_y|;
near-zero benefit on Mach-E (no real cornering). Cost: ~80-120 LOC for
`st_model.py` and integration with `generate_simdata_ford.py`.

**H3. Steady-state understeer-gradient correction (poor-man's ST).** Apply
`psi_dot_corrected = psi_dot_KS / (1 + K_u * v^2)` where K_u is an understeer
gradient calibrated per platform from the data (or computed analytically from
`m, l_f, l_r, C_af, C_ar`: `K_u = m/L^2 * (l_r/C_af - l_f/C_ar)`). Captures
most of ST's high-speed gain droop with one scalar and zero new state. Cost:
~15 LOC. Expected ~70-80% of ST's benefit on the gain problem.

**H4. Steering-compliance lag/filter on delta.** Signature: cross-correlation
of delta_road and psi_dot_meas peaks at non-zero lag (saw 0-4 samples on most
segments, 25 on one — possibly periodic wrap, suspicious). Mechanism: steering
column / rack compliance + measurement latency means commanded delta leads
achieved slip-angle response. Fix: low-pass delta_meas or shift by N samples.
Expected small effect (~5-10% RMSE reduction at most).

**H5. Wheelbase / steering-ratio recalibration.** Use measured (v, delta,
psi_dot) on quasi-steady turns to fit an effective L (or effective i_s).
Likely tiny — parameters come from openpilot carParams which are usually
right within a few percent. Expected ~2-5% improvement, low priority.

**H6. Wheel-speed v vs IMU-integrated v.** Skill notes wheel-speed
overestimates on slipping wheels. Probably small in these segments (no hard
accel/regen events visible). Low priority.

## 4. Open questions

- Is the F-150 large straight-line psi_dot bias (-1.49 deg/s on seg1) really
  sensor bias, or is there a temperature-dependent steering-angle offset
  feeding through? Could fit both simultaneously (yaw-bias + steering-bias).
  Need to check adapter for any delta centering.
- Does `simulate_ks` permit a corrected psi_dot output without rewriting the
  integrator? Yes — `psi_dot` and `a_y` are derived **post-hoc** from the
  state at line 185-186 of `ks_model.py`, so they're easy to intercept
  *outside* `simulate_ks` in `generate_simdata_ford.py` for H1/H3.
- For ST: do `MachEST` / `F150LightningST` constants give numerically stable
  integration at 50 Hz with RK4, or does the stiffness term require
  sub-stepping? Check eigenvalues after writing the dynamics; if unstable,
  fall back to H3 (understeer correction) as the lateral fidelity bump.
- References to load in Phase 2: full body of `skills/vehicle-dynamics-rlog`
  for the ST equations / fidelity-ladder details, `code/ks_model.py` (already
  read in phase 1), `code/parameters.py` (already read), 
  `code/generate_simdata_ford.py` (already read for hook points).
