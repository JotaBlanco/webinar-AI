# Final model — idea-01 lateral fidelity

Per-platform algebraic correction layered on V0 yaw rate.

Variants selected per platform on dev CTE-RMSE:
- FORD_F_150_LIGHTNING_MK1: V4  (a*yp + b*yp*v^2)
- FORD_MUSTANG_MACH_E_MK1:  V2  (a*yp + b*yp^3)
- HYUNDAI_IONIQ_5:          V4  (a*yp + b*yp*v^2)
- TESLA_MODEL_3:            V0  (passthrough; pred == truth in shared sim)

See the top-level REPORT.md (one directory up) for full numerical results,
methodology, and self-critique.
