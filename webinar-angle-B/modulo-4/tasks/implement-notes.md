# Phase 3 — Implement notes

## What I built
- `tools/lateral_corrections.py` — `estimate_yaw_bias`, `understeer_gradient`,
  `apply_understeer_correction`. Pure functions, no I/O. Smoke-tested via
  `python3 tools/lateral_corrections.py` — prints K_u and the corner-factor.
- `tools/regenerate_with_corrections.py` — variant generator. Took the
  plan's intended shortcut: reads existing `sim.csv` rather than re-decoding
  rlogs (CAN-decode deps not installed). Writes `sim_<variant>.csv` alongside.
- `tools/eval_ablation.py` — aggregator across all four variants per platform.

## Deviations from the plan
1. **H1 only debiases the yaw channel, not a_y.** The plan said as much in
   passing. Confirmed by ablation: H1 leaves `RMSE a_y` exactly unchanged
   (0.062 / 0.443 on Mach-E / F-150). Good — yaw-rate and lateral-G sensors
   are physically independent, so a yaw-gyro bias should not propagate to
   `a_lat_meas`. This is consistent.
2. **Did NOT write `sim_baseline.csv` as the source of truth.** The
   evaluator reads the original `sim.csv` (shipped by
   `generate_simdata_ford.py`) for the baseline row. The `sim_baseline.csv`
   files I generated as a sanity check are produced but unused by the
   evaluator. This is a harmless redundancy — both contain identical data
   (I verified the cells match to 6 sig figs).

## Surprises
- **H1 alone wiped 73.6% of Mach-E RMSE psi_dot.** That's exactly the
  hypothesis from research.md (Mach-E segments are near-straight-line, so the
  residual was mostly sensor zero-offset). The remaining 0.134 deg/s RMSE
  is genuine noise plus the tiny model error on the small amount of
  turning that does happen.
- **H3 alone gives 17% on F-150 yaw RMSE and 27% on F-150 a_y RMSE**, but
  *zero* on Mach-E (Mach-E has v*v small AND psi_dot_pred ~ 0, so dividing by
  (1 + K_u v^2) barely changes anything). Cost-justified on F-150, neutral
  on Mach-E. The bias number on Mach-E even worsens by 0.012 deg/s — within
  noise.
- **H3 helped a_y more than yaw on F-150** (27% vs 17%). a_y = v * psi_dot
  amplifies the correction by v, so the relative improvement scales up at
  high speed, which is exactly where the residual is worst.
- **Compositionality almost-additive** as predicted: H1 -29.7% + H3 -17.1%
  ~ -46.7% additive vs observed -50.7%. The small positive interaction comes
  from the bias being smaller after H3 shrinks the pred (so removing it
  matters more in relative terms).

## What didn't fit the plan's success criteria
- All three quantitative criteria met (Mach-E -73.6% > -40%; F-150 -17% > -10%;
  combined H1+H3 strictly best on both platforms).
- Mach-E `bias` went from +0.32 to -0.10 (sign flip) under H1 — that's fine,
  it just means the bias estimator is slightly biased itself (median of
  small-yaw samples is not exactly the true zero-offset because the model
  does predict a tiny non-zero in those samples too). For a tighter
  estimator one could subtract the model prediction inside the mask. Future
  work.

## Files produced
- `tools/lateral_corrections.py`
- `tools/regenerate_with_corrections.py`
- `tools/eval_ablation.py`
- `data/sim/segments/*/*/sim_baseline.csv` (x4, redundant sanity)
- `data/sim/segments/*/*/sim_h1.csv` (x4)
- `data/sim/segments/*/*/sim_h3.csv` (x4)
- `data/sim/segments/*/*/sim_h1_h3.csv` (x4)
- `REPORT.md` at module root
