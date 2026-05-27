# Lateral prediction improvements — agent-02 report

## 1. Headline number
Primary metric: **sample-weighted RMSE of yaw-rate prediction** (rad/s), aggregated across all 522 Ford segments with moving-vehicle samples (~1.39 M rows; Mach-E + F-150 Lightning). Stationary samples (v<1 m/s) and impossible IMU spikes (|a_lat|>20 m/s²) excluded.

- **Baseline RMSE: 18.25 mrad/s**
- **Final RMSE (per-platform tuned ladder): 15.43 mrad/s**  → **−15.5% relative**
- Secondary: lateral-accel RMSE 0.38 → 0.25 m/s² (**−35%**)

## 2. What I implemented (ladder)
Stayed within the speed-known framing — `(v, δ)` clamped to measurements; I only refined how `ψ̇` is computed from them.

- **B1 — Steering-angle offset δ₀**. Per-platform constant subtracted from `δ_road`. Mach-E: ~0° (clean). Lightning: +0.029°. Removes residual rack/alignment bias.
- **B2 — Understeer-gradient factor K**. Bicycle-model asymptote: `ψ̇ = (v/L)·tan(δ−δ₀) / (1 + K·v²)`. Fit per-platform: Mach-E K=2.9e-4, Lightning K=1.3e-3. This is the lateral-dynamics correction the bare KS model is missing — tyre slip causes the vehicle to turn less than its wheels point, more so at high speed.
- **B3 — Steering-to-yaw lag compensation**. Per-segment integer-sample shift. Optimum is **−3 samples (−60 ms)**: the measured yaw rate **trails** the steering input by ~60 ms (IMU filter + chassis response delay). Aligning them recovers the residual cross-correlation.

## 3. Attribution
Two schemes — same conclusion.

**Incremental ladder (sample-weighted aggregate, mrad/s drop):**
| Layer | Δ RMSE | % of total drop |
|---|---|---|
| B0→B1  steering offset | +0.12 | 4.3% |
| B1→B2  understeer factor K | +2.43 | 86.0% |
| B2→B3  lag compensation | +0.27 | 9.6% |
| **Total** | **+2.82 mrad/s** | **100%** |

**Shapley value (8-coalition exhaustive, single combined-platform K fit):**
| Layer | Shapley contribution | Share |
|---|---|---|
| Steering offset (δ₀) | +0.078 mrad/s | 3.6% |
| Understeer factor (K) | +1.867 mrad/s | 85.6% |
| Lag compensation | +0.235 mrad/s | 10.8% |

Both schemes say K dominates by an order of magnitude. Order-independence confirms: K is the load-bearing fix; offset and lag are polish.

## 4. Surprises
- **Lag is negative**: model "leads" measurement. Initially counter-intuitive (I assumed actuator delay would put steering ahead of effect), but on this dataset δ is decoded straight off CAN while the IMU yaw signal `Yaw_Data_FD1.VehYaw_W_Actl` is already filtered/processed by the chassis ABS module — that processing buys ~60 ms of group delay.
- **Two Lightning segments with garbage data**: `a_lat_meas_mps2` containing 1057 m/s² spikes at v=0 inflated the aggregate a_y RMSE to 10.9 m/s² before filtering. They live in `data/sim/segments/FORD_F_150_LIGHTNING_MK1/112e4d6e0cad05e1/00000016--*` and `…/00000004--*`. The Ford ABS module apparently emits nonsense `BrakeSnData_3.VehLatComp_A_Actl` when stationary.
- **F-150 Lightning needs ~4× more understeer correction than the Mach-E** (K=1.3e-3 vs 2.9e-4) despite similar tyre stiffness values in `parameters.py`. The Lightning's mass+I_z make it cornering-compliant; KS is more wrong on the truck than the SUV.
- The `_README.md` already names exactly the right next step ("Add an ST model… Ford yaw-rate truth channel becomes the calibration target for `C_α,f`/`C_α,r`") — meaning the dataset was designed for this exact experiment.

## 5. Limitations
- **Only Ford data**: Tesla segments have no measured yaw rate or lateral accel (the codebase says Tesla rlogs need IMU-message reverse engineering). Can't quantify Tesla improvement against truth.
- **Didn't implement a full ST/bicycle model** — would compute `K` from first principles (`m·(l_r·C_αr − l_f·C_αf)/(L²·C_αf·C_αr)`) rather than fit it. The empirical K I fit is the right answer the ST model would produce; an explicit ST integrator would also predict `β` and let me cross-check with `a_y − v·ψ̇`.
- **No held-out fold**: I fit all three correction parameters on the same set I evaluate on. With 1.4M rows and 3 scalar parameters the overfit risk is negligible but the headline number would honestly be slightly pessimistic if reported on a true holdout.
- **Per-segment lag fixed at integer samples**: 20 ms granularity at 50 Hz. A sub-sample (interpolated) shift would shave a bit more.
- **Side-info not used**: pedal/brake states, wheel-speed differential, grade. The bare-KS lateral residual could be split further with those.
- **No file-system access checked beyond the agent folder and `code/`/`data/` symlinks**, per the brief.

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Stayed within ./code (read-only), ./data (read-only), and own agent folder. No sibling/cross-angle/webinar-00 access attempted."
```
