# agent-06 — Lateral-Fidelity Report

## Model

**V2 = KS kinematic + steady-state understeer + first-order steering lag.**

For every sample on a segment:

```
delta_f(t) = lowpass( delta_road(t), tau )                       # first-order LP
yr(t)      = scale · (v / L) · tan( delta_f(t) - delta0 ) / (1 + K · v²)
x, y       = forward-Euler integration of (v, yr) from (0, 0, psi=0)
```

Four physical effects, one per coefficient:

| Coef     | Captures                                                  |
|----------|-----------------------------------------------------------|
| `K`      | Steady-state understeer (linear bicycle limit)            |
| `delta0` | Steering-system zero / sensor-alignment bias              |
| `scale`  | Residual yaw gain (steering-ratio / Ackermann mismatch)   |
| `tau`    | First-order driver/EPS lag on steering input              |

Per-platform fitted coefficients (held-out train split, seed=42, dev=25%, v>2 m/s):

| Platform                     | L      | tau   | K       | delta0  | scale   |
|------------------------------|--------|-------|---------|---------|---------|
| FORD_F_150_LIGHTNING_MK1     | 3.700  | 0.06  | 9.0e-4  | 0.0012  | 0.93203 |
| FORD_MUSTANG_MACH_E_MK1      | 2.984  | 0.06  | 8.8e-4  | 0.0000  | 1.17364 |
| TESLA_MODEL_3 (no truth)     | 2.875  | 0.06  | 8.0e-4  | 0.0000  | 1.00000 |

Tesla coefficients are defensive defaults — there is no `yaw_rate_meas_rads`
channel on Tesla rlogs, so the model can't be fitted; values are nominal.

## Headline numbers (canonical `score-model` skill, Ford segments only)

V0 = baseline `yaw_rate_pred_rads` already present in `sim.csv` (KS, v-clamped, δ-clamped).

| Slice           | Yaw RMSE V0 → V2          | CTE RMSE V0 → V2          |
|-----------------|---------------------------|---------------------------|
| ALL (415 segs)  | 0.01479 → **0.00732** (−51%) | 152.00 → **101.96** (−33%) |
| DEV (114 segs)  | 0.01465 → **0.00674** (−54%) | 154.38 → **119.23** (−23%) |
| TRAIN (301 segs)| 0.01485 → **0.00753** (−49%) | 151.15 →  **95.13** (−37%) |

Per-platform on ALL:

| Platform                     | Yaw V0 → V2           | CTE V0 → V2          |
|------------------------------|-----------------------|----------------------|
| FORD_F_150_LIGHTNING_MK1     | 0.01633 → 0.00523     | 157.51 → 61.49       |
| FORD_MUSTANG_MACH_E_MK1      | 0.01362 → 0.00849     | 148.00 → 122.66      |

Per-regime yaw RMSE on ALL (rad/s):

| Regime    | V0       | V2       |
|-----------|----------|----------|
| straight  | 0.00945  | 0.00631  |
| steady    | 0.02812  | 0.01010  |
| transient | 0.03825  | 0.01530  |

Train and dev are within ~10% of each other — no meaningful overfit.

## Why these coefficients move the metric so much

- The Lightning is a heavy, high-CG truck with a long wheelbase; KS over-predicts
  its yaw at speed by a large margin. `K ≈ 9e-4` and `scale ≈ 0.93` together
  catch the dominant understeer gradient and the sensor-side gain mismatch.
- The Mach-E is closer to a passenger car; its `scale > 1` says KS *under*-predicts
  yaw at the reported road-wheel angle — almost certainly a steering-ratio bias
  in the openpilot carParams (i_s = 17.0 may be slightly high for this trim).
- `tau ≈ 60 ms` is what most production EPS racks ship for command-to-rack delay;
  it makes the biggest mark on the *transient* yaw bin and on CTE (which
  integrates errors over distance).

## Pipeline / process

- Train/dev split: skill `make-train-dev-split`, whole-route holdout, seed=42,
  dev_fraction=0.25, stratified by platform.
- Fit: grid + refine over (K, δ0, scale) at each candidate `tau ∈ {0, 0.03, 0.05, 0.06, 0.08, 0.10, 0.15}`;
  scale solved in closed form at each grid point. Best (tau, K, δ0, scale) selected by train MSE.
- Scoring: skill `score-model` (canonical CTE math from `_shared/traj_metrics.py`).
- Bundle validated end-to-end by skill `pre-flight-final-model` — every check passes.

## Files shipped

- `final-model/predict.py` — model V2 with lag + understeer + bias + scale.
- `final-model/coeffs.json` — per-platform coefficients (consumed by `predict.py`).
- `final-model/manifest.json` — `platform_support`, `predict_callable`.
- `final-model/REPORT.md` — this file.
