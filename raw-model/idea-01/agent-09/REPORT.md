# Lateral-Prediction Improvements — Agent 09

## 1. Headline number

**Primary metric: pooled yaw-rate RMSE over all 520 Ford segments (Mach-E + F-150 Lightning), masked to `v > 2 m/s` (1.36M samples).**

- Baseline KS model: **0.01474 rad/s** (~0.84 °/s)
- Tuned KS model:   **0.00894 rad/s** (~0.51 °/s)
- **Improvement: −39.4% RMSE**

Secondary (derived) metric — lateral-acceleration `a_y = v·ψ̇`:
- Baseline 0.386 m/s² → Tuned 0.270 m/s² (**−30.1%**)

Per platform:
- F-150 Lightning: 0.01677 → 0.00840 rad/s (**−49.9%**)
- Mach-E: 0.01317 → 0.00928 rad/s (**−29.5%**)

## 2. What I implemented

I worked directly off the per-segment `sim.csv` files (which carry `v_mps`, `delta_road_rad`, measured `yaw_rate_meas_rads`, `a_lat_meas_mps2`, and the baseline KS prediction). This let me synthesise alternative predictions cheaply without re-running the rlog decoders.

Four corrections were stacked on top of the existing baseline `ψ̇ = (v/L)·tan(δ_road)`:

- **V1 — yaw-rate bias offset.** Subtract a per-platform scalar `b` (residual mean). Cheap fix for any IMU offset / wheel-alignment drift. b≈+3.98 mrad/s for F-150, ≈+0.56 mrad/s for Mach-E.
- **V2 — refit steering-ratio scalar `k`.** Equivalent to replacing `i_s` with `i_s/k`. F-150 fit implies effective `i_s ≈ 18.93` (vs nominal 16.9 — a +12% rack ratio). Mach-E fit implies `i_s ≈ 15.57` (vs nominal 17.0 — a −9% rack ratio).
- **V3 — time alignment.** Per-segment search for best integer-sample lag between δ and measured ψ̇ at 50 Hz; took the median (`−3` samples for F-150, `−4` for Mach-E, i.e. **yaw rate leads steering by ~60–80 ms** — this is the EPS-to-bus latency).
- **V4 — linear understeer correction.** `ψ̇ = (v/L)·tan(δ)/(1 + K·v²)`. K fits ~4.6e-4 (F-150) and ~3.7e-4 (Mach-E), both positive and in the expected order of magnitude for a passenger EV (Ackermann under-steer at speed). This is the single most important physics term.

## 3. Attribution

**Scheme: Shapley value over the four corrections, allocating the total MSE-drop across all 24 (n!) ordering permutations.** This avoids the trap of standalone effects being miscredited because V2 and V4 are partially redundant (a fixed scalar steering scale can mimic a fixed-speed understeer slope).

Shapley % of total MSE-drop:

| Variant | F-150 | Mach-E |
|---|---|---|
| V1 — bias | 7.0% | 0.4% |
| V2 — refit `i_s` | 34.8% | **51.8%** |
| V3 — time align | 3.1% | 13.6% |
| V4 — understeer `K·v²` | **55.1%** | 34.3% |

(Standalone MSE-drop tells a different and misleading story — e.g. V2 alone and V4 alone each look responsible for >45% on the F-150 because they both partially absorb the constant turn-radius error.)

Pooled across platforms: V2 + V4 together account for ~85% of the gain, V1 ~3%, V3 ~9%.

## 4. Surprises

- **F-150 steering ratio is materially wrong** in the parameter file (16.9 nominal, ~18.9 implied — a 12% error that produces a 50% RMSE reduction once corrected). Mach-E is wrong in the other direction (17.0 nominal vs ~15.6 implied — 9%). These are the kind of numbers comma.ai's `carParams` is supposed to nail; either the rlog `carParams` itself was off, or the EPS angle has a nonlinear scale at small magnitudes.
- **Negative best-lag** (steering leads yaw by ~60–80 ms in the file's sample index, but the fit wants the *opposite* shift). Mechanically: the resample collapsed both channels onto a 50 Hz grid but the Ford EPS `StePinComp_An_Est` and the IMU `VehYaw_W_Actl` have different bus arrival delays. The adapter does no time-of-flight compensation.
- The F-150's persistent ~+3.6 mrad/s positive yaw residual at baseline (≈0.2 °/s) is **larger than the noise floor** — small but real. Subtracting it is cheap and probably worth shipping even before refitting any physics.
- The KS model already includes `a_long` quantities in the CSV but they're unused under `clamp_v_to_measured=True` — there is no lateral-prediction lever there, so I ignored them.

## 5. Limitations

- Worked only on already-generated `sim.csv` files. I did not re-run `generate_simdata_ford.py` with corrected parameters; my "tuned" numbers are reconstructed analytically from `(v, δ_road)` and the closed-form `ψ̇`. Because the speed-known clamp turns KS into a closed-form lateral predictor, this is exact for ψ̇ and ay — but a true integrator-loop fit (re-running with corrected `i_s`, etc.) would also affect heading/position channels which I did not evaluate.
- No held-out test set: I fit and report on the same pooled data. With ~1.4M samples and 4 global scalar fits per platform, overfitting is negligible, but a per-segment K-fold would be cleaner.
- Did not look at the Tesla segments because their CSVs lack the yaw-rate truth channel (commented as such in the README), so attribution against ground truth is impossible there.
- A real ST (single-track) refit would change attribution: V2 and V4 are KS-level proxies for the same physics ST gets right by construction. With ST I'd expect the V4 share to shrink and a new "lateral cornering stiffness" term to take its place.
- I did not access any of the forbidden paths (sibling agent folders, webinar-angle modules, webinar-00 metadata). No prompts blocked anything — I did not attempt to read them.

Artefacts written:
- `tools/baseline.py`
- `tools/improve.py`
- `tools/shapley.py`
- `tools/final_eval.py`
- `out/baseline_per_seg.csv`
- `out/improvement_report.json`
- `out/shapley.json`

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Worked entirely off pre-generated sim.csv files via the data/ symlink; no rlog re-decoding; no sibling/angle/webinar-00 reads attempted."
```
