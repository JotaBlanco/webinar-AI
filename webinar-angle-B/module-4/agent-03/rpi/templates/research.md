# Research — `rpi/runs/<timestamp>/research.md`

> Fill this out before proposing any fix. The Research phase constitutes the problem. No solutions yet.

## Setting

- Platform scored:
- Number of segments:
- Number of samples:

## Operating contract restated

- Which channels are **clamped** (inputs):
- Which channels are **predicted** (outputs under test):
- The residual under test:

## Baseline (V0) — no preprocessing

- Overall RMSE on `yaw_rate_resid_rads`:
- Per regime (define regimes here):
  - Straight:
  - Steady cornering:
  - Transient cornering:

## Sign-convention sanity

- `corr(delta_road_rad, yaw_rate_meas_rads)` on cornering samples: (positive expected)

## Plausible failure modes (don't fix yet — just enumerate)

- 
- 
- 

## Open questions

- 
- 

## What I would want next (a wishlist, for the post-mortem)

- 
