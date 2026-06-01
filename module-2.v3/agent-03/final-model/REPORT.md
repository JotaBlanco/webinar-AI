# final-model bundle

V4 lateral-fidelity model. See ../REPORT.md for full discussion.

Headline scores (full sim dataset, all platforms):
- yaw_rate_rmse = 0.006613 rad/s  (V0 baseline 0.012934)
- cte_rmse     = 78.82 m         (V0 baseline 163.83 m)

Model form per platform:
  yr = v * (delta - delta_off - c3 * delta^3) / (L + K_us * v^2)
       + tau * d(delta)/dt + bias

Tesla is passthrough of V0 (its truth channel IS the V0 KS output).
Coefficients in coeffs.json, fitted with L-BFGS-B on route-grouped
80/20 train-dev split, objective = yaw RMSE.
