# final-model/REPORT.md — agent-10 (m4.v2.01)

Bundle-local report required by preflight. See the agent-level REPORT.md for the full debrief.

## Shipped
- `predict.py:predict` — re-exports `code/v1_baseline.predict_v1`.
- Backing TREE.json node: `v1-baseline-leader` (rung 0, verdict `promote_to_leader`).

## Pooled dev scores (frozen split, this template's `_shared/frozen_split.py`)
- Yaw RMSE: 0.005430 rad/s
- CTE RMSE: 52.215 m
  - Tesla contributes zero error by construction (no independent truth).

## Rung-climb attempts logged
- M1 (linear dynamic single-track, rung 1) — fit aborted at ~10 min wall-clock under shared-machine contention. Priors give yaw RMSE ~0.0095 (worse than V1).
- M4 (relaxation-length, rung orthogonal) — fitted sigma per platform (0.31 m IONIQ, 0.40 m Mach-E, 0.40 m F150 with wide_train_dev_gap warning). Pooled yaw 0.005634, CTE 52.105 — yaw regressed +3.8 %, CTE basically tied.

## Platform support
All four. Tesla falls through to V0 passthrough inside predict_v1.
