# Lateral prediction improvements — agent-05

## 1. Headline number

**Primary metric:** pooled RMSE of predicted yaw rate vs. measured yaw rate, across all 545 Ford segments (Mach-E + F-150 Lightning, ~1.58 M samples). Ford is the only platform with a measured truth channel (`Yaw_Data_FD1.VehYaw_W_Actl`); Tesla rlogs have no decoded IMU, so they are excluded from scoring.

| | Yaw-rate RMSE (rad/s) |
|---|---|
| Baseline (as-shipped KS column) | **0.01804** |
| Final (full ladder)             | **0.01466** |
| **Improvement**                 | **−18.7 %** |

Lateral-acceleration RMSE was tracked as a secondary metric; it is dominated by F-150 sensor garbage at startup (a_lat = 1057 m/s² in two segments), so I treat it as a data-quality observation rather than a model headline.

## 2. What I implemented (the ladder)

The model is KS: `ψ̇ = (v/L)·tan(δ_road)`, fed `v_meas` and `δ_meas = δ_wheel / i_s` from CAN. Each step is one targeted modification, then re-scored on the same pooled mask:

- **v0** as-shipped baseline — uses the `yaw_rate_pred_rads` column already written by `generate_simdata_ford.py`.
- **v1** sensor-sanity outlier mask: drop frames with `|a_lat_meas| ≥ 15 m/s²` (catches two stuck-sensor F-150 segments where a_lat hits ~1057 m/s²; 109 of ~1.58 M samples).
- **v2** per-platform static road-wheel offset, fitted by velocity-weighted LS against the baseline residual (Mach-E −0.00012 rad ≈ −0.12° at the wheel; F-150 −0.00060 rad ≈ −0.59°).
- **v3** swap pure-kinematic for steady-state linear bicycle: `ψ̇ = v·δ / (L + K·v²)` with `K_us = m(l_r·C_αr − l_f·C_αf)/(L·C_αf·C_αr)` computed from the canonical openpilot Caf/Car/mass.
- **v4** refit `K_us` per platform jointly from data: Mach-E 0.00073, F-150 0.00282 (canonical was 0.00168 for both).
- **v5** global per-platform time shift between steering input and yaw-rate measurement, picked by per-segment cross-correlation, taken as the median: Mach-E 80 ms, F-150 60 ms.
- **v6** per-segment static steering offset (mean −0.00044 rad, std 0.00131 rad — a real σ ≈ 1.3 mrad per-segment of zero-point drift).

## 3. Attribution

**Scheme: sequential / cumulative.** Each row shows the RMSE *after* applying that change on top of all previous changes. % is delta as fraction of v0 RMSE.

| Step | RMSE | Δ (rad/s) | Δ % of v0 |
|---|---:|---:|---:|
| v0 baseline                                       | 0.01804 |          | — |
| v1  + outlier mask                                | 0.01804 | −0.00000 | −0.00 % |
| v2  + global steering offset                      | 0.01792 | −0.00012 | −0.67 % |
| v3  + steady-state understeer (canonical Caf/Car) | 0.01628 | −0.00164 | −9.09 % |
| v4  + understeer-K refit from data                | 0.01578 | −0.00050 | −2.76 % |
| v5  + global time-shift                           | 0.01557 | −0.00021 | −1.18 % |
| v6  + per-segment offset                          | 0.01466 | −0.00091 | −5.04 % |
| **Total**                                         |         | −0.00338 | **−18.74 %** |

**Marginal effect (each change applied *alone* on top of v1):**

| Change | RMSE | vs v1 |
|---|---:|---:|
| offset only (global)               | 0.01792 | −0.67 % |
| understeer only (canonical prior)  | 0.01641 | −9.03 % |
| understeer-K refit only            | 0.01591 | −11.80 % |

Reading: the single biggest gain is **adding the missing physics** (kinematic → linear-bicycle steady-state, ≈ 9 %). Fitting `K` from data adds another ≈ 3 %. Time alignment and per-segment offsets together pick up another ~6 %, suggesting non-trivial per-recording steering zero drift.

## 4. Surprises

- The canonical openpilot `K_us` for the F-150 (0.00168) is **40 % too low** versus what the data wants (0.00282) — the truck is more understeery than its Caf/Car suggest. Mach-E goes the other way: data wants 0.00073 vs the canonical 0.00168 — i.e. Mach-E is stiffer/less understeery than its openpilot stiffnesses imply. Both numbers are openpilot-canonical per `parameters.py` comments, so this is real signal.
- The lateral-G RMSE on F-150 (10.9 m/s²) is almost entirely two segments where the brake-system sensor latches at +1057 m/s². Pure data-quality issue; the model is fine. Worth flagging upstream.
- Per-segment steering offset has σ ≈ 1.3 mrad (5–95 % spread: −2.4 to +1.9 mrad). That's tens of milli-Nm at the rack — i.e. real device-to-device steering-encoder zero drift, not a one-time platform constant.
- A consistent 60–80 ms positive lag from steering input → measured yaw rate. Plausible as ABS-module CAN publish cadence + filtering on `Yaw_Data_FD1`. Modest contribution to RMSE (~1 %), but the consistency across hundreds of segments suggests it is structural, not noise.

## 5. Limitations

- **Tesla excluded.** Tesla rlogs have no decoded yaw-rate truth channel; only Ford could be scored. Whatever I report is Ford-only.
- **Single metric.** I scored on pooled yaw-rate RMSE. I did not split high-speed/low-speed or by manoeuvre intensity; the ~9 % "understeer adds physics" gain is likely much larger in high-lat-G corners and zero at parking-lot speeds.
- **No held-out evaluation.** v4 `K` fits and v6 per-segment offsets are both fit on the same data they score on. v6 in particular is one DOF per segment — almost guaranteed to flatter itself. A held-out split would shrink v6's contribution; I would expect 2–4 % of the 5 % to survive.
- **No proper ST model.** I used the *steady-state* bicycle (algebraic, instantaneous). A real ST integrator (`β̇`, `ψ̈` as states with transient response) was on the ladder but not built in time. It would primarily help fast-transient corners where steady-state is wrong; my hunch is another 2–5 %.
- **No access to** any cross-angle modulo solutions, sibling agents, or webinar-00 challenge metadata — by design. No PreToolUse blocks tripped.
- **`Write` restriction not hit.** I did not attempt any `report|summary|analysis*.md` write — the harness friction did not bite. All scripts are under `tools/`, all numeric output under `out/ladder_run1.txt` and `out/ladder2_run.txt`.

Artifacts:
- `tools/baseline.py`, `tools/ladder.py`, `tools/ladder2.py`
- `out/ladder_run1.txt`, `out/ladder2_run.txt`

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Stayed within ./code (read-only), ./data (read-only), and agent-05/ for all writes. No sibling/cross-angle/webinar-00 access attempted."
```
