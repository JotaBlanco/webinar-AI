# Agent 02 — raw-model / idea-02

## Headline number

**Primary metric: open-loop one-step `a_long` prediction RMSE on held-out segments.**
- Baseline ("integrate sensed IMU `a_long`"): closed-loop full-segment v_RMSE ≈ **2.6 m/s mean / 1.9 m/s median** over ~58 s. The trivial "use the crutch" baseline is 0 by construction.
- Our model (predicts `a` from commanded inputs, then integrates): open-loop a_RMSE = **0.62 m/s² (a_MAE 0.42)**; closed-loop v_RMSE = **6.5 m/s mean / 5.4 m/s median** at full 58 s horizon; at 5 s horizon RMSE = **2.1 m/s**, at 1 s horizon RMSE = **0.5 m/s**.

## What I implemented

1. **Linear `a_long` regressor** over commanded inputs only: `a_pred = cP·accel_pct + cPv·accel_pct·v + cB·brake·v + rV·v − kAero·sign(v)·v² + c0`. Fit by lstsq on 80% of Ford segments (1.26 M samples).
2. **Closed-loop integrator** (forward-Euler, dt = 0.02 s) where the only state is `v_pred`; features at each step are recomputed from `v_pred`, never from `v_meas`. Initial `v_pred = v_meas[0]`. Speed clipped to [0, 50] m/s for numerical sanity.
3. **Multi-horizon sliding-window eval** (1, 2, 5, 10, 20 s windows) to characterise drift growth.

## How I validated

- **Open-loop one-step (a-channel):** at each tick predict `a_pred(t) = f(accel_pct(t), brake(t), v_meas(t))`, compare to IMU `a_long_meas(t)`. Inputs: `accel_pedal_pct` (commanded), `brake_pressed` (commanded), `v_meas` (sensed — used here only because this is open-loop). Test set is unseen Ford segments. **MAE 0.42, RMSE 0.62 m/s².**
- **Closed-loop integration (v-channel):** integrate `v_pred` forward using only `accel_pct` and `brake` (both **commanded**) and the *state* `v_pred` (never `v_meas` after t=0). Horizons: terminal-error sliding eval at H ∈ {1, 2, 5, 10, 20} s plus full-segment integration (~58 s).
- All inputs to the closed-loop model are **commanded** (`accel_pedal_pct`, `brake_pressed`); `v_meas` is used only to seed `v_pred[0]` and as truth.

## Regime breakdown (closed-loop v_RMSE, full segment, m/s)

| regime | n_segs | v_RMSE mean |
|---|---|---|
| cruise | 106 | 6.46 |
| accel  | 72  | 4.81 |
| brake  | 27  | 5.13 |
| coast  | 73  | 6.92 |
| stop   | 42  | 4.22 |

Coast is the worst regime — lift-off regen (which scales with v and pack SOC) is not captured by my flat-linear form. Accel and brake are best because the driver-command signal is strong and the model has a direct term for it.

**Terminal-v error vs horizon (60 segments, sliding window):**

| horizon | mean |err| | RMSE | p50 | p90 |
|---|---|---|---|---|
| 1 s | 0.36 | 0.51 | 0.24 | 0.88 |
| 2 s | 0.69 | 0.97 | 0.46 | 1.68 |
| 5 s | 1.55 | 2.12 | 1.13 | 3.53 |
| 10 s | 2.69 | 3.47 | 2.19 | 5.47 |
| 20 s | 4.43 | 5.41 | 3.80 | 9.14 |

Error grows roughly linearly with horizon — characteristic of any open-loop dead-reckoning longitudinal predictor without ground-speed feedback.

## Surprises

- The repo's `_README.md` explicitly frames the **whole workshop as "speed-known lateral-only"** — `simulate_ks(clamp_v_to_measured=True)` is the canonical mode. The brief's "remove the crutch" is therefore literally a documented next-step (item 4 in "Next sessions" — longitudinal decomposition).
- The Ford CSVs already break out `a_long_mps2` from IMU, plus `accel_pedal_pct` and `brake_pressed` — i.e. the dataset is shaped exactly for this task. (Tesla CSVs lack a clean brake-pressure / pedal signal of the same fidelity, which is why I stuck to Ford only.)
- `brake_pressed` is **binary** in this dataset (from `BpedDrvAppl_D_Actl >= 2`). With no brake-pressure analog, the model can't distinguish a hint of brake from emergency stop — this caps brake-regime accuracy hard.
- The naive "integrate IMU `a_long`" baseline beats my model on long-horizon v_RMSE (2.6 vs 6.5 m/s). That makes physical sense: IMU `a_long` is the actual realised force/mass, including grade — my model has no grade input and is throttle-only.

## Limitations

- **Tesla excluded**: Tesla CSVs have `di_torque_actual_nm` and `brake_pedal_state` but not the same clean ApedPos as Ford. A multi-platform model would need a per-platform input mapping; I had no time.
- **No grade signal**: the residual between IMU a_long and any drivetrain model is dominated by road grade. Without an inertial estimate or map data we will always have a ~0.2 m/s² constant-offset error in `a` → ~12 m/s error after 60 s.
- **No regen model**: lift-off regen on EVs is large (often 1–2 m/s²); my single `rV·v` term is a crude proxy.
- **Binary brake** as noted.
- **Linear model only**: a small MLP on `(accel_pct, brake, v, ap_dot, brake_dot)` would likely cut open-loop a_RMSE from 0.62 to ~0.3 m/s² — didn't have time.
- No harness friction encountered — no `Write` calls were blocked. Did not attempt to write a `*.md` report file; this response is the report.

## Files produced

- `tools/load_segments.py`
- `tools/long_model.py`
- `tools/short_horizon_eval.py`
- `tools/plot_one.py`
- `out/summary.json`
- `out/closed_loop_seg_{0..5}.png`

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Stayed within ./code (read-only browse) and ./data. No writes to shared dirs. Did not access webinar-00/, sibling agent folders, other raw-model/idea-*/, or webinar-angle-*/ modules."
```
