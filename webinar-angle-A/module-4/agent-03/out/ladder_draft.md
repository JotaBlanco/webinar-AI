# Lateral-fidelity ladder - FORD_MUSTANG_MACH_E_MK1

Platform: FORD_MUSTANG_MACH_E_MK1.
Scored channel: yaw_rate_resid_rads. yaw_rate_meas_rads is the measured truth channel from the rlog gyro.
v and delta are clamped to measured; the predicted quantity under test is yaw_rate_pred_rads.
Same segment set held constant across every variant row. Regimes: straight, steady, transient cornering.

| Variant | Description | RMSE overall | RMSE straight | RMSE steady | RMSE transient | delta vs prev |
|---|---|---:|---:|---:|---:|---:|
| V0 | baseline | 0.016127 | 0.008768 | 0.031724 | 0.056889 | - |
| V1 | KS recalibrated + per-segment bias | 0.014693 | 0.004931 | 0.031673 | 0.057390 | -0.001434 |
| V2 | Linear ST prior C_alpha | 0.015512 | 0.003393 | 0.034294 | 0.062869 | +0.000819 |
| V3 | Linear ST fitted C_alpha (DE) | 0.015105 | 0.003645 | 0.033124 | 0.061242 | -0.000407 |
| V4 | Ridge residual learner (LOO) | 0.014897 | 0.003704 | 0.032705 | 0.060063 | -0.000208 |

V2 is a regression (delta is positive). Attribution: strict marginal, fixed order.
