# Research — lateral-fidelity challenge

## Operating contract
- KS model in speed-known lateral-only mode (`clamp_v=True`, `clamp_delta=True`).
- Predicts `psi_dot = (v/L) * tan(delta_road)`; `a_y = v * psi_dot` (coupled).
- Truth: `yaw_rate_meas_rads`, `a_lat_meas_mps2` (Ford only).
- Scored channel by team: `yaw_rate_resid_rads`.

## Baseline numbers (V0, no preprocessing, full segment set, per-regime)

| Platform                  | Segments | Samples | overall | straight | steady  | transient |
|---------------------------|---------:|--------:|--------:|---------:|--------:|----------:|
| FORD_MUSTANG_MACH_E_MK1   |      315 |  913626 | 0.01613 |  0.00878 | 0.03147 |   0.05743 |
| FORD_F_150_LIGHTNING_MK1  |      230 |  667141 | 0.02037 |  0.00899 | 0.03629 |   0.05161 |

(Numbers from `evals/baseline_rmse.py` and confirmed by `tools/ladder.py`.)

## Failure-mode hypotheses
1. **Steering sensor zero** — small constant bias on `delta_road_rad` → constant yaw-rate error proportional to v.
2. **Understeer** — KS assumes zero side-slip; real cars need `psi_dot = v*delta / (L + K_us*v^2)`. Front-tire understeer gradient `K_us > 0` shrinks predicted yaw vs KS at speed. Heavier rear-biased Lightning likely shows this strongly.
3. **Phase lag** — measurement / actuator pipeline can introduce a few-sample lag between commanded `delta` and measured `psi_dot`.
4. **`a_y` coupling** — anything we do to `psi_dot` must be reflected in `a_y = v*psi_dot`.

## Schema-check observation
`evals/schema_check.py` FAILS on stored CSVs: stored `yaw_rate_resid_rads = meas − pred`,
not `pred − meas` as the team convention says. This is the exact failure ratchet item #1
warns about — but it is irrelevant to RMSE (sign squared away) and does NOT affect the
V0 numbers. Flagged for the team.
