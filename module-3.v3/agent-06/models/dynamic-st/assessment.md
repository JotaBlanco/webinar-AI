# dynamic-st — assessment

Pooled dev (with per-platform affine post-fit): yaw 0.006549, CTE 58.98.
Without affine post-fit: yaw 0.009322, CTE 66.54.

Per-platform (with affine):
- Lightning: yaw 0.00744, cte 73.59, cte_signed −12.15
- Mach-E: yaw 0.00902, cte 97.08, cte_signed −19.66
- IONIQ-5: yaw 0.00853, cte 72.63, cte_signed −12.59

Verdict: LOSS vs V1.

Diagnosis:
- Integrator OK (no overflow after sub-stepping).
- Root cause: under-parameterised vs *fitted* V1. V1's K_us is data-fit; the
  rung-1 K_us_dyn derived from carParams Iz / C_α is systematically lower.
- The cohort failure mode in m3.v2 (rung-1 attempts losing to V1) reproduces
  here for exactly the reason `references/dynamics-formulations.md` predicted:
  "rung-1 yaw RMSE worse than rung-0 ceiling because rung-0 had per-platform
  fit and the rung-1 attempt didn't".
- Path forward: fit C_αf, C_αr, Iz from data (probably with one fixed and
  the ratio constrained). Out of time budget for this run.
