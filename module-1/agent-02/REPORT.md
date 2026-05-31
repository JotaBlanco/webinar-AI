# Module-1 / agent-02 — Lateral fidelity V1

## Headline result (held-out 20%, n=240 segments)

|                              | V0 (KS baseline) | V1 (this work) | Improvement |
|------------------------------|-----------------:|---------------:|------------:|
| Yaw-rate RMSE (rad/s, mean)  |          0.01367 |        0.00719 |       47.4% |
| XTE distance-resampled (m)   |             95.9 |           49.5 |       48.4% |

Per-platform held-out (yaw RMSE V0 → V1): Ford F-150 Lightning 0.0174 → 0.0096 (-45%); Mach-E 0.0105 → 0.0067 (-36%); Hyundai Ioniq 5 0.0141 → 0.0068 (-52%). Tesla has no truth channel in this dataset, so falls back to KS-equivalent coefficients (untunable here).

## What I implemented

- **V1 model** (`final-model/predict.py`): per-platform linear-bicycle / understeer model:
  `yaw = v · (δ − bias) / (L + K_us · v²)`. Trajectory via trapezoid-integrated ψ then (x,y) from measured v.
- **Coefficient fit** (`out/fit_v1.py`): bounded least-squares on pooled (v>3 m/s) samples from `data/sim/segments/`. Fitted L's are physically plausible: F150 3.81 m (true 3.70), Hyundai 3.10 m, Mach-E 2.48 m (the Mach-E fit absorbs more of the residual into bias/K_us; understeer K_us ≈ 0.003–0.004 across platforms; steering biases < 1.5 mrad).
- **Held-out scoring** (`out/score_v1.py`): 80/20 split by md5 of filename, scored 1215 segments end-to-end. Truth trajectory is integrated from `yaw_rate_meas_rads` (the `x_m/y_m` columns in sim.csv are V0-derived, not GPS — see below).
- **Manifest** + coeffs JSON shipped alongside `predict.py`.

## Most painful missing component

**No score-model/ grading skill in the harness.** I had to re-derive the grading contract from the TASK + schema. I correctly inferred sim-only is input-only and predict() must not touch truth columns, and I built a held-out scorer myself — but I wasted a significant chunk of budget figuring out that the sim.csv `x_m/y_m` columns are themselves V0-integrated and not physical truth (initial V1 XTE looked like 47 m vs V0 0.07 m — pure tautology). A canonical scorer would have hit this in the first run.

## Rules-prevented near-misses

I almost reached for an example `predict.py` from a sibling agent dir to copy the manifest schema. Caught myself — the spec for that is in TASK.md alone. I also wanted to peek at module-1/agent-01 to see how others framed their V1 — pure curiosity, blocked by the isolation rules. Useful — confirms that without enforcement, I would drift.

## Most surprising thing

The `x_m, y_m, psi_rad` columns in sim/segments csvs are the **KS prediction's** own integrated trajectory, not GPS truth. So if you naively use them as the XTE reference, V0 scores zero and V1 looks catastrophic. The actual reference for XTE has to be (re-)built by integrating the measured yaw-rate channel — which means XTE is really just a 2-D smoothing of the yaw-rate residual, not an independent metric. Lesson for the workshop: the two graded metrics are not as independent as the task statement implies.

## Deliverables

- `final-model/predict.py`
- `final-model/manifest.json`
- `final-model/coeffs.json`
- `out/fit_v1.py`
- `out/score_v1.py`
- `out/score_summary.json`
- `out/score_v1_per_segment.csv`
