# Implement notes — 20260527-160000

## Per-variant log

### V1 — per-platform constant yaw-rate bias
- Implemented as: `b = median(train.yaw_rate_resid_rads)`; subtract from pred on TEST.
- Result Mach-E: overall 0.01613 → 0.01614 (essentially flat). Lightning: 0.02037 → 0.02006 (mild).
- Surprise: bias on Mach-E is tiny (-7.5e-4 rad/s) and median ≈ mean of residual already centred. The "constant gyro bias" hypothesis FAILED on Mach-E (no payoff). On Lightning b ≈ -4.4e-3 rad/s and gives a small straight-regime improvement.

### V2 — per-segment yaw-rate bias
- Implemented as: `b_seg = median(train.resid)` per `__seg__`; map to TEST.
- Result Mach-E: overall 0.01613 → 0.01462 (-9.4%); straight 0.00878 → 0.00507 (-42%).
- Result Lightning: overall 0.02037 → 0.01938 (-4.9%); straight 0.00899 → 0.00706 (-21%).
- Surprise: per-segment is much larger than per-platform. The straight-regime error is dominated by **per-segment** IMU zero, not a platform constant. This is calibration, not a model improvement — flagged in REPORT.

### V3 — per-platform steering gain k
- Implemented as: LS fit of `meas = k · (v·δ/L)` on cornering samples in TRAIN.
- Result Mach-E: k=1.110, overall 0.01613 → 0.01594 (-1.2%), steady -3.9%, **transient -11.5%**.
- Result Lightning: k=0.892, overall 0.02037 → 0.01698 (-16.6%), steady -19.9%, transient -13.1%.
- Surprise: gains diverge sharply across platforms — Mach-E ψ̇ is under-predicted by ~11%, Lightning over-predicted by ~11%. The shipped steer-ratio (17.0 vs 16.9) is too close to explain the spread; the right knob is an effective rack-compliance multiplier, not the gear ratio.
- The painful absence here: KS has no tire side-slip, so k absorbs both rack compliance AND understeer at speed — V3 is the only handle KS gives us.

### V4 — per-platform affine (k·δ + d0) plus pred bias b
- Implemented as: joint LS `meas = k·(v·δ/L) + d0·(v/L) + b`.
- Result Mach-E: k=1.081, d0=-3.5e-4 rad, b=1.65e-3 rad/s. Overall 0.01579 (-2.1%). Transient -9.2% (slightly worse than V3 alone).
- Result Lightning: k=0.882, d0=-8.5e-5 rad, b=-3.4e-3 rad/s. Overall 0.01654 (-18.8%).
- Near-miss: V4 was supposed to beat V3 strictly. On Mach-E the joint fit moved k from 1.110 to 1.081 because the bias term absorbed some of the gain's contribution — net effect: marginally better overall but transient regressed vs V3. Honest read: the per-platform bias adds almost no information once steering gain is in.

## Deviations from the plan
- None on ordering. Plan asked for held-out interleaved TEST RMSE; all numbers above are TEST.
- V1 result on Mach-E essentially null — kept in ladder per "lock the plan" rule even though it falsifies the gyro-bias hypothesis for that platform.

## Numerical results table (per-regime RMSE per variant)

Mach-E (per-platform fit, except V2 per-segment):

| Variant | overall | straight | steady | transient | scope |
|---------|--------:|---------:|-------:|----------:|-------|
| V0 baseline           | 0.01613 | 0.00878 | 0.03147 | 0.05744 | — |
| V1 platform bias      | 0.01614 | 0.00875 | 0.03155 | 0.05750 | per-platform |
| V2 segment bias       | 0.01462 | 0.00507 | 0.03111 | 0.05756 | per-segment (calibration) |
| V3 steering gain k    | 0.01594 | 0.00999 | 0.03024 | 0.05085 | per-platform |
| V4 affine + bias      | 0.01579 | 0.00959 | 0.03011 | 0.05214 | per-platform |

Lightning:

| Variant | overall | straight | steady | transient | scope |
|---------|--------:|---------:|-------:|----------:|-------|
| V0 baseline           | 0.02037 | 0.00899 | 0.03629 | 0.05161 | — |
| V1 platform bias      | 0.02006 | 0.00799 | 0.03634 | 0.05161 | per-platform |
| V2 segment bias       | 0.01938 | 0.00706 | 0.03516 | 0.05128 | per-segment (calibration) |
| V3 steering gain k    | 0.01698 | 0.00786 | 0.02907 | 0.04485 | per-platform |
| V4 affine + bias      | 0.01654 | 0.00655 | 0.02883 | 0.04540 | per-platform |

## Regressions flagged
- V3 raises **straight** RMSE on Mach-E (0.00878 → 0.00999). Physical cause: k>1 amplifies tiny δ-jitter noise around zero; the gain helps cornering but hurts straight-line where the multiplicative effect on near-zero δ is dominated by noise.
- V4 slightly worsens **transient** vs V3 on Mach-E. The bias term steals variance from the gain, weakening the cornering correction.

## Schema_check status
- `evals/schema_check.py` PASSED on both `out/v4_sample_FORD_MUSTANG_MACH_E_MK1.csv` and `out/v4_sample_FORD_F_150_LIGHTNING_MK1.csv`. Sign convention preserved; a_y_pred re-derived per rule 9.

## Things I would change about harness / data / skills
- An ST (dynamic single-track) rung with cornering stiffness would attack the transient residual that V3 can only partially absorb.
- Per-segment IMU zero (V2 finding) suggests a pre-processing step belongs upstream of `generate_simdata_ford.py` — calibrate gyro zero from the first N straight seconds of each segment.
