# Lateral-prediction improvement report — agent-01

## 1. Headline number

**Primary metric:** pooled yaw-rate RMSE (rad/s, reported in deg/s), on Tesla Model 3 segments, activity-masked (v ≥ 5 m/s **and** |ψ̇_truth| ≥ 2 deg/s; n ≈ 85 300 samples across 120 segments).

**Baseline (KS as-shipped) → final (all three corrections):**
**2.763 deg/s → 2.547 deg/s** (–0.215 deg/s, **–7.8 %**).

R² of yaw rate against truth proxy: **0.838 → 0.861**.
Improvement is concentrated in the 5–20 m/s band (≈ 12–20 % RMSE reduction); at highway speed (>30 m/s) the gain shrinks to ~2 %.

## 2. What I implemented (ladder)

The model under attack is the existing CommonRoad KS predictor: `ψ̇ = v · tan(δ) / L`, with `v` and `δ` clamped to measurements (speed-known lateral-only mode). Three additive corrections:

- **C1 – effective steer-ratio (α).** Replace `δ` with `α · δ`. Globally fitted α = **0.866**, meaning the openpilot-canonical steer ratio i_s = 12.0 should effectively be **13.86** against this truth proxy. KS over-steers by ~15 %.
- **C2 – steady-state understeer (Kᵤ).** Bicycle-model correction: divide ψ̇ by `(1 + Kᵤ · v² / (g·L))`. Fitted Kᵤ = **0.0060** (rad of equivalent steer per g of lateral accel), a small but consistent positive understeer.
- **C3 – steering→yaw first-order lag (τ).** Butterworth low-pass on predicted ψ̇ at fc = 1/(2πτ). Best τ = **0.10 s**.

## 3. Attribution

**Scheme: Shapley value on RMSE reduction**, computed over the full 2³ = 8-subset power set of {C1, C2, C3}. Each subset's RMSE was evaluated independently; Shapley credit averages each correction's marginal contribution across all join orders.

| Correction | Shapley credit (deg/s reduction) | Share |
|---|---|---|
| **C1 (effective steer-ratio α)** | **+0.155** | **71.9 %** |
| **C2 (understeer Kᵤ)** | **+0.056** | **25.9 %** |
| **C3 (lag τ)** | **+0.005** | **2.2 %** |

Cumulative (waterfall) accounting agrees to within 1 percentage-point — most of the value is in α; Kᵤ helps mainly at high speed; τ is in the noise.

## 4. Surprises

- **The truth channel is missing.** The dataset's rlogs do *not* contain `sensorEvents` / `liveLocationKalman` / `carState` — the comma3 was passively logging the bus without controlsd/locationd. There is no IMU yaw-rate truth at all. I had to fabricate one from the rear wheel-speed differential `(v_RL – v_RR) / track_rear` with `track_rear = 1.580 m` (public Tesla M3 spec). This is the same workaround the adapter docstring flags as an open problem.
- **Sign convention is flipped between the Tesla CAN steering signal and the wheel-speed channel.** Cross-correlating the existing `psi_dot_rads` column against the wheel diff was strongly positive for `RL – RR` (not `RR – RL`) — so either the openpilot Tesla DBC is exposing `SCCM_steeringAngle` with the opposite sign to the rest of openpilot, or the wheel labels FL/FR/RL/RR are reversed left-for-right. The KS code happens to be self-consistent because it never compares to wheel data; the moment you do, the sign bites.
- **Openpilot's canonical steerRatio (12.0) is ~15 % too low** against the rear-wheel-diff truth on this fleet. That's a big, easily-recoverable error and explains why a naive KS dramatically overshoots ψ̇ on every corner.
- **The fleet's understeer gradient is small but positive** (Kᵤ ≈ 0.006), in line with a sportier sedan setup; it only starts mattering above ~20 m/s.
- **τ ≈ 0.10 s of effective steering→yaw lag** is consistent with EPS+chassis filtering, but barely worth modelling here.

## 5. Limitations

- **No ground-truth yaw rate.** The wheel-speed differential is the only available proxy; it conflates wheelspin/ABS events and rolling-radius asymmetries with real yaw. RMSE numbers are absolute against that proxy, not against IMU truth.
- **Track-width is assumed** at 1.580 m. Any error there scales every RMSE figure by the same multiplicative factor — the *relative* attribution and the α / Kᵤ / τ fits are robust to this, but the absolute headline isn't.
- **Single platform.** I ran only on Tesla Model 3 (120 of 1025 available segments, strided across devices for diversity). The same ladder should be repeated on the Mach-E and F-150 Lightning, which the codebase clearly supports.
- **No train/test split.** All fits were on the full sample given the 15-min budget. Held-out R² would be lower but the qualitative ranking of corrections should hold.
- **The CommonRoad ST (single-track-with-tires) rung exists in `parameters.py` but no implementation was found in the codebase.** Going beyond α / Kᵤ corrections would mean implementing the dynamic bicycle model with `C_alpha_f`, `C_alpha_r`, `m`, `I_z` (all already in `parameters.TeslaModel3ST`). That is the obvious next step and would test whether the apparent "α=0.866" is really a fixed steer-ratio bias or whether it's masquerading for tire slip-angle dynamics.
- **No access to the canonical solution** (`webinar-00/`, `webinar-angle-*/modulo-*/`) by experimental contract; I have no idea whether my α ≈ 0.87 / Kᵤ ≈ 0.006 are anywhere near the workshop's intended answer.

### Outputs persisted

- `tools/analyze_lateral.py`, `tools/ladder_v2.py`, `tools/scatter_diag.py`, `tools/check_signs.py`
- `out/subset_rmse.csv`, `out/shapley.txt`, `out/fit_params.txt`, `out/ladder_results.csv`

### Harness friction

No `Write` was blocked. I did not attempt to write a `REPORT.md`-shaped file — full content is above.

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Truth channel had to be synthesised from rear-wheel-speed differential because the rlogs in data/ contain no IMU/locationd events. Sign convention between steering and wheel-speed signals is flipped in this dataset — verified by correlation, not from documentation."
```
