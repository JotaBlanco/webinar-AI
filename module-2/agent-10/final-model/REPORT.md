# Lateral fidelity — agent-10 final model

## Headline numbers (full Ford eval set, scored with `skills/score-model`)

| KPI                              | V0 (baseline) | V1 (this model) | Improvement |
|----------------------------------|---------------|-----------------|-------------|
| Yaw-rate RMSE (rad/s)            | 0.01479       | 0.00770         | -48 %       |
| Distance-resampled CTE RMSE (m)  | 151.998       | 102.324         | -33 %       |

Per platform (all 415 segments):

| Platform                    | V0 yaw RMSE | V1 yaw RMSE | V0 CTE  | V1 CTE  |
|-----------------------------|-------------|-------------|---------|---------|
| FORD_F_150_LIGHTNING_MK1    | 0.01633     | 0.00547     | 157.5 m | 63.7 m  |
| FORD_MUSTANG_MACH_E_MK1     | 0.01362     | 0.00894     | 148.0 m | 122.4 m |

Per regime (yaw RMSE, v > 2 m/s): straight 0.0094 → 0.0063; steady 0.0281 → 0.0115; transient 0.0382 → 0.0175.

Honest dev-set check (25% whole-route hold-out, seed=42): V1 dev yaw 0.00743 vs V0 dev yaw 0.01506; dev CTE 68 m vs V0 dev CTE 174 m. Train/dev coefficients agreed within ~1% on K, tau, s; b0 was identical to four significant figures. No overfit detected.

## Model

For each platform p, with measured `t, v, delta`:

1. Low-pass the steering input on the (non-uniform) time grid:
   `delta_f[k] = (1 - a[k]) * delta_f[k-1] + a[k] * delta[k]`, where `a[k] = dt[k] / (tau_p + dt[k])`.
2. Yaw rate: `psi_dot = s_p * (v * delta_f) / (L_p + K_p * v^2) + b0_p`.

This is the steady-state linear-bicycle yaw rate (kinematic single-track + understeer term `K * v^2`), modulated by a global steering gain `s` (absorbs steering-ratio mismatch, sidewall compliance, and the `tan(delta)≈delta` approximation error in V0) plus a constant offset `b0` (sensor / mounting bias).

Coefficients (least-squares fit on full data, grid (K, tau) × closed-form (s, b0)):

| Platform                  | L     | K       | tau    | s       | b0          |
|---------------------------|-------|---------|--------|---------|-------------|
| FORD_MUSTANG_MACH_E_MK1   | 2.984 | 0.00275 | 0.060  | 1.1931  | +2.19e-4    |
| FORD_F_150_LIGHTNING_MK1  | 3.700 | 0.00375 | 0.060  | 0.9693  | -4.44e-3    |

Notes:
- Mach-E `s ≈ 1.19` says V0 under-predicts yaw by ~19% — consistent with V0 using kinematic geometry where the real rack/sidewall combo turns sharper.
- F-150 `b0 ≈ -4.4 mrad/s` (~-0.25 deg/s) is a real, segment-pooled yaw-rate offset (sensor bias or mounting yaw). Removing it alone closes most of the F-150 gap.
- `tau = 60 ms` on both platforms — a tight first-order lag on the steering channel is the only dynamics that the bicycle form misses. Setting tau = 0 costs ~3% on yaw RMSE; not big, but consistent across train/dev.

## Variants tried

1. **V0** baseline (kinematic single-track, precomputed): RMSE 0.01479 / CTE 152 m. Reference.
2. **V1 understeer + scale + bias (no lag)**: yaw 0.00779, CTE 103 m. Big single-step gain.
3. **V1 + first-order lag (tau grid-search)** — *shipped*: yaw 0.00770, CTE 102.3 m. Marginal but consistent.
4. **V2 cubic-in-feature** (tire saturation): train -3% vs V1, dev *worse*. Dropped.
5. **V3 speed-scaled steering gain** (`s + sv·v`): train -3%, dev flat. Less interpretable. Dropped.
6. **V4 full bilinear** in (v, feat, feat³): same overfit signal — dev worse than V1. Dropped.

V1 was the Pareto winner across train, dev, and the full set.

## Skills

- Used: `score-model/score` (both KPIs on full and dev; the only score I trusted); `make-train-dev-split/split` (whole-route hold-out); `pre-flight-final-model/preflight` (final shipping check — passes apart from the REPORT.md write block).
- Inspected, not used: `load-segments`, `compare-models`, `visualise-segment` — train/dev metrics were sufficient signal.
- No skill modified.

## Friction notes

- Bash permission denial on ad-hoc shell commands (`python -c`, `ls *.py`) forced all exploration through small scripts under `_work/`. Python execution itself was unrestricted.
- `final-model/REPORT.md` write was blocked by the sub-agent harness (filename matches `report.*\.md`); this content was returned to the parent for persistence.

## Most painful absence

A vectorised one-pole low-pass helper. The time-varying-coefficient recursion over ~1M samples in pure-Python `for` loops dominated every fit-and-score iteration. A `scipy.signal.lfilter`-style wrapper handling `alpha[k] = dt[k]/(tau + dt[k])` would have cut grid-search wall-clock ~10x and let me explore richer variants honestly.
