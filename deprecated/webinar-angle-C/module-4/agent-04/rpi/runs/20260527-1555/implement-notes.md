# Implementation notes (20260527-1555)

## Key findings

- **Sign-convention drift in source CSVs.** `yaw_rate_resid_rads` in
  `data/sim/segments/.../sim.csv` equals `meas − pred`, not the team's
  documented `pred − meas`. `evals/schema_check.py` reports FAIL on raw CSVs
  (max diff ~1.4e-1). RMSE is unaffected (squaring kills the sign) but any
  downstream code that reasons about residual *sign* will be inverted. My
  ladder computes `pred − meas` directly, so attribution is correct.

- **Mustang vs F-150 want opposite gain corrections.**
  - Mustang Mach-E: k = 1.094 → KS under-predicts yaw by ~9%.
  - F-150 Lightning: k = 0.867 → KS over-predicts yaw by ~13%.
  Both are per-platform fits (not per-segment) — this is a real model
  calibration, not a sensor offset memorisation. Most plausible physical cause:
  the steering-rack ratio / wheelbase used by KS (`PARAM_BY_PLATFORM` in
  `code/parameters.py`) is off, larger for the truck.

- **Lag alignment regresses on both platforms.** Best shift is −1 sample
  (−20 ms) but TEST RMSE worsens by 0.0002. KS prediction is already
  time-aligned with measurement; the residual autocorrelation tricks a
  contiguous search but interleaved-split TEST RMSE catches it. Reported as
  regression with physical cause: clamped `v, δ` integrator has no lag to fix.

- **Bias removal helps F-150 (+0.00031), regresses on Mustang (−1e-5).**
  F-150 has a small yaw-rate sensor zero offset (~4.4 mrad/s). Mustang's
  median is already ~0.75 mrad/s — within noise.

- **V4 speed-residual is marginal.** Both platforms get sub-1e-4 marginal —
  most of the structure is absorbed by V3.

## Total improvement (TEST set, overall RMSE)

| Platform | V0 | V4 | Drop |
|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | 0.01613 | 0.01585 | +1.7% |
| FORD_F_150_LIGHTNING_MK1 | 0.02037 | 0.01662 | +18.4% |

Attribution coherence on both platforms: 0.000 (well under 0.15 tolerance).

## Schema check

`evals/schema_check.py` FAILS on stock `sim.csv` because of the residual-sign
discrepancy described above. Not a regression I introduced; flagged for
follow-up — either fix `generate_simdata_ford.py` to emit `pred − meas`, or
update the schema check to accept `meas − pred`. Per ratchet rule #1, the
CSV writer is the bug.
