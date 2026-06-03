# Final-model bundle — M4 relaxation-length

Predict: `predict.py:predict`. Coeffs: `coeffs.json`.

Shipped: orthogonal-rung relaxation-length tire on V1 kinematic core.
Fitted per-platform sigma on frozen train split (1187 segments) via
1D grid search; sigma_F150 = 0.4 m, sigma_MachE = 0.4 m, sigma_Hyundai = 0.3 m.

Pooled dev: yaw 0.005631 rad/s, cte 52.10 m (vs V1 dev 0.005430 / 52.22).
Near-tie with V1; M4 wins CTE marginally and loses yaw marginally.

See top-level REPORT.md for the workshop write-up.
