# Agent 09 — raw-model / idea-02

# Longitudinal model — drop the v-clamp crutch

## 1. Headline number

- **Primary metric:** closed-loop integrated speed RMSE over a 5 s horizon (the rung that matters for short-term planning).
- **Baseline (hold v(0)):** 5 s RMSE ≈ 4-5 m/s for typical segments (full-segment hold RMSE: **7.58 m/s Tesla, 6.01 m/s Mach-E, 6.53 m/s F-150**).
- **Final (learned a(p,b,v) + Euler integrate):** 5 s RMSE = **1.07 m/s (Tesla)**, **0.98 m/s (Mach-E)**, **1.14 m/s (F-150)**. At 10 s: 1.9 / 2.1 / 1.7 m/s.
- Open-loop one-step a-residual RMSE: **0.50 / 0.46 / 0.54 m/s²** across the three platforms.

## 2. What I implemented

- A **8-feature ridge-regressed parametric a-model**: `a_long = θ·[1, v, v², p, p·v, brake, brake·v, lift·v, lift]` where `p = accel_pedal_pct/100` and `lift = 1{p<0.02}` captures the EV regen lift-off term. Fit per-platform, no cross-platform sharing.
- A **closed-loop integrator** (forward Euler, dt = `sim.csv` cadence ≈ 20 ms, with saturation `a ∈ [-10, 8] m/s²` and `v ∈ [0, 70] m/s`) that takes only commanded inputs `(accel_pedal_pct, brake_pressed)` plus its own integrated v — no measured speed used after t=0.
- A unified `get_brake()` shim — Tesla's `brake_pedal_state` is constant 2 in the rendered sim CSVs (no signal), Ford uses a 0/1 `brake_pressed` column; the model degrades gracefully when brake info is degenerate.
- Train/test split: 70/30 over up to 80 segments per platform, random shuffle, seed=0.
- Physical-outlier filter on training and eval data (`v∈[0,80) m/s`, `|a|<12 m/s²`) — caught some F-150 segments with huge a-glitches that otherwise gave a-RMSE of 23 m/s².

## 3. How I validated

- **Mode A — open-loop one-step:** at each sample, feed the model `(p_meas, brake_meas, v_meas)` and compare predicted vs measured `a_long`. All inputs sensed, no integration.
- **Mode B — closed-loop integration:** start from `v(0)=v_meas(0)`; at every step feed `(accel_pedal_pct, brake_pressed)` (commanded driver inputs) and the model's own running `v` state. Compared against (a) `v_meas`, (b) hold-v(0) baseline, (c) oracle "integrate measured a_long" baseline.
- Horizons reported: 5 s, 10 s, 30 s, full-segment (~60 s).

## 4. Regime breakdown (one-step a-residual)

| platform | accel | cruise | coast | brake | other |
|---|---|---|---|---|---|
| Tesla | 0.70 (bias −0.39) | 0.26 (≈0) | 0.19 (−0.10) | n/a | 0.82 (+0.36) |
| Mach-E | 0.82 (−0.34) | 0.35 (+0.06) | 0.35 (+0.20) | 0.31 (+0.07) | 0.62 (+0.23) |
| F-150 | 0.70 (−0.39) | 0.33 (+0.04) | 0.29 (−0.26) | 1.30 (+0.54) | 0.57 (+0.16) |

RMSE in m/s²; bias is the mean signed residual. Pattern: **accel under-predicted (negative bias) and brake decel under-predicted (positive bias)** — the linear pedal-to-force map cannot capture the EV's torque flattening at high pedal nor the heavy F-150's brake authority. Cruise and coast are essentially clean.

## 5. Surprises

- Tesla `brake_pedal_state` in the produced sim.csv was constant **2** across every segment I sampled (the `brake` and `brake*v` columns trained to exactly 0.0 because of perfect collinearity with degenerate input). Tesla's "decel" signal lives entirely in regen-during-lift-off — captured by the `lift` and `lift*v` features.
- F-150 raw data has occasional `a_long` spikes far exceeding physical limits (>10× normal); even the **oracle "integrate measured a"** baseline gave full-segment RMSE = 164 m/s before I added the filter. The data isn't clean.
- The **Mach-E closed-loop full-segment RMSE explodes (16 m/s)** despite the best one-step error (0.46 m/s²). A small positive bias in the "coast" regime (+0.20 m/s²) integrated over 60 s is enough to push the predicted v up by ~12 m/s — a classic open-loop drift signature.
- The 5 s closed-loop RMSE (~1 m/s for all three) is much better than the full-segment numbers suggest. The model is genuinely useful for short-horizon planning; long-horizon drift is the dominant failure.

## 6. Limitations

- **No access to MPC/planner-commanded acceleration.** The "commanded" inputs available in `sim.csv` are driver pedal/brake — already an actuator-level abstraction. Real autonomous-driving usage would feed `(a_cmd, brake_cmd)` from a planner; I can't validate that path.
- **No drivetrain-torque feedforward.** `di_torque_actual_nm` is logged for Tesla but is an effector output, not a command — using it as an input would just be relabelling the crutch. A proper model would estimate it from `(pedal, v)` and then feed torque into the longitudinal balance.
- **No road-grade or wind.** Pure flat-earth assumption. Drift behaviour on hilly segments will be worse than this RMSE suggests.
- **Linear/affine model.** Insufficient at the extremes (heavy accel, hard brake). A piecewise or small MLP would close the regime-specific bias gaps, but I prioritised an explainable, fittable-on-a-laptop baseline.
- **Tesla brake signal degenerate** in the sim.csv mirror. The raw rlog likely carries useable brake info (e.g., wheel-speed deceleration vs no-pedal); didn't have time to bypass `generate_simdata.py` and pull it.
- **No subset/stratified test by trip length** — my closed-loop RMSE pools 60 s segments, where the integrator drift dominates over the model fit.

### What I'd want next

- Brake-pressure (not just on/off) from Tesla rlog, or use wheel-speed deceleration as a brake proxy.
- A grade signal from the IMU/locationd to subtract gravity component before fitting.
- Saturation-aware loss (Huber) so accel/brake extremes drive parameter updates more.
- Joint validation against the lateral model — that's the system-level metric that actually matters for closed-loop trajectory tracking.

### Harness friction

Nothing blocked me. I did not attempt to write any `report*.md` / `summary*.md` / `analysis*.md` / `findings*.md` files; this report is delivered verbatim in the final response. Wrote `tools/build_long_model.py`, `tools/plot_traces.py`, `out/long_model_results.json`, `out/long_model_traces.png` only.

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Stayed within agent folder, ./code/, ./data/."
```
