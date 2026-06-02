# affine-v1 — formulation

`yaw_pred = a · yr_V1 + b` per platform.

State-space: none — pure post-correction of V1's output.
Integrator: n/a.
Priors: (a, b) fit by OLS on (V1 yr, truth yr) with v>5 m/s filter.
Expected residual character: removes per-platform mean residual and corrects a
systematic gain miscalibration in V1.
