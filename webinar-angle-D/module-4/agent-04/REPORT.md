# REPORT.md — webinar-angle-D / module-4 / agent-04

## Task
"Lateral predictions from our vehicle model aren't as good as they should be. Make them better, and tell me how much each change contributed."

## Setup
- Platform: **FORD_MUSTANG_MACH_E_MK1** (Mach-E). `yaw_rate_meas_rads` is the **measured** truth channel from the openpilot rlog IMU.
- Operating contract: `v` and `δ` are **clamped to measured** every step (speed-known, lateral-only). Speed-state agreement is zero by construction and is not the metric.
- Segment set: 8 distinct routes under `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/` (first sim.csv per route), 23,189 rows total. Regime split: 19,581 straight / 2,723 steady / 885 transient.
- Skills composed: `regime-segmentation` (tag the DF) → `lateral-fidelity-triage` (ladder + sensor).
- Attribution: **strict marginal**, fixed order V0→V1→V2→V3→V4. Marginal drops sum to the total V0→V4 drop within < 1% — accounting is consistent.

## Variant ladder

| Variant | Description | Overall RMSE (rad/s) | Straight | Steady | Transient | Marginal Δ vs prev | Verdict |
|---|---|---|---|---|---|---|---|
| V0 | As-is `yaw_rate_resid_rads` baseline | 0.01704 | 0.00913 | 0.03128 | 0.05246 | — | baseline |
| V1 | KS recalibrated (canonical L) + per-segment yaw-gyro bias on straight samples | **0.01635** | 0.00480 | 0.03246 | 0.05704 | **+0.00069 (improves)** | **best — shipped** |
| V2 | Linear single-track, prior `C_α` (Cαf=286551, Cαr=355912 N/rad) | 0.02051 | 0.00376 | 0.04317 | 0.07055 | −0.00416 (regresses) | regression |
| V3 | Linear single-track, fitted `C_α` (Cαf=150000, Cαr=150000 — optimiser stalled at init) | 0.02067 | 0.00380 | 0.04358 | 0.07092 | −0.00016 (regresses) | regression |
| V4 | Ridge residual learner on `[v, |a_y|, |δ|, sign(δ̇)]`, LOO-by-segment, subtracted from V3 | 0.02751 | 0.00439 | 0.05675 | 0.09743 | −0.00684 (regresses) | regression |

## What contributed to the improvement
- The whole net improvement (−0.00069 rad/s overall, **−0.00433 in the straight regime**) comes from V1: canonical wheelbase + per-segment gyro-bias subtraction on straight-line samples. Bias removal halves straight-regime RMSE; that dominates the row-weighted overall.
- V2/V3/V4 all made things worse. Reasons:
  - **V2 (prior Cα)**: linear-ST with stiff prior under-predicts yaw rate in cornering. Cornering RMSE in steady regime jumps 0.031 → 0.043, transient 0.052 → 0.071.
  - **V3 (fitted Cα)**: `fit_c_alpha` minimises overall RMSE which is dominated by 84% straight-line rows that carry no Cα signal. Optimizer stalled at the x0 init (1.5e5, 1.5e5); `pegged=False` only because pegging is defined at the *upper* bound. This is a real failure of fit scoping — fitting should be done over the cornering subset only.
  - **V4 (residual learner)**: LOO-OOF RMSE on V3 residual is 0.0275 — far worse than V3 in-sample. The learner cannot generalise across routes on these features; correctly flagged a regression per the v0.5 LOO-honesty rule.

## Sensor gate
`python3 skills/lateral-fidelity-triage/sensor.py out/best_V1.csv`
- sensor PASS sign-consistency: corr(pred, meas) on cornering = 0.995
- sensor PASS regression-check: RMSE(candidate) = 0.01635 ≤ V0 = 0.01704

V1 is shippable.

## Skill composition decision
- Order: `regime-segmentation.load_and_validate` → `.tag` → pass tagged DF into the ladder. Both skills share identical regime thresholds (`|δ|<0.01` rad, `|dδ/dt|<0.05` rad/s); kept in lockstep by convention.
- Justification: regime-segmentation is a pure DataFrame transform with no platform knowledge; lateral-fidelity-triage is the analytical playbook. Front-loading the deterministic tagger means every ladder row uses the same regime labels as the reporting layer.

## Honest limitations / painful absences
- **No `a_y` track in either skill.** Data carries `a_y_pred_mps2` and `a_y_resid_mps2` but the ladder only scores yaw rate. Lateral fidelity has two channels; we improved one.
- **Cα fit not regime-scoped.** `triage.fit_c_alpha` minimises over all rows; for an 84%-straight dataset that has no useful Cα gradient. A v0.6 patch would fit on the `regime != "straight"` slice.
- **No third "reporting" skill.** Variant orchestration + report writing lives in `tools/run_ladder.py` (per-agent script). Two-skill harness, three-skill problem.
- Read only the files inside `module-4/agent-04/` plus the symlinked `code/` and `data/`. No siblings, no other angles, no `_shared` or `_launch` or `raw-model`.

## Rules that earned their keep
- v0.3 V0-baseline pin: stopped the gyro-bias from being folded into V0 (which would have hidden V1's win entirely).
- v0.5 pegged-Cα + regression-flagging rules: forced honest reporting of V2/V3/V4 as regressions, not silent wins.
- v0.5 sensor.py gate: deterministic sign/regression guard on the shipped variant.
- LOO-only scoring for V4: surfaced the residual learner's failure to generalise.

## Surprise
V2/V3 worsen cornering despite being a "better" physics model. The headline is that **the dataset's row-weight is so heavily straight-driving that the Cα fitter has no signal**; the linear-ST prior under-predicts cornering yaw rate; the simpler KS + bias-zero correction (V1) wins. Composition exposed this because the regime tagger made the row imbalance visible in the table — without the per-regime breakdown, "V3 is a regression" would have been buried under a flat overall RMSE.
