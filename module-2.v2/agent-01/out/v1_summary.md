Found 1996 segments
## score-model summary
- n_segments: 1996 (failed: 0), n_samples: 5,193,632
- **yaw_rate_rmse**: 0.006533 rad/s
- **cte_rmse**: 79.0583 m

### 🚨 signed-bias check — read this BEFORE you ship
CTE is a double-integral of yaw error and is dominated by *systematic* bias, not RMS noise. If a row below is flagged, fit that calibration — don't tune yaw RMSE harder.

| platform | yaw_bias (rad/s) | yaw bias_frac | cte_drift (m) | flag |
|---|---|---|---|---|
| `FORD_F_150_LIGHTNING_MK1` | -0.00000 | 0.00 | +4.000 | ok |
| `FORD_MUSTANG_MACH_E_MK1` | +0.00000 | 0.00 | -2.901 | ok |
| `HYUNDAI_IONIQ_5` | -0.00000 | 0.00 | -5.358 | cte_drift ⚠️ |
| `TESLA_MODEL_3` | +0.00000 | nan | +0.000 | ok |

Thresholds: yaw_bias |·| > 0.002 rad/s, cte_drift |·| > 5.0 m. '⚠️' = above threshold; '🚨' = above 3× threshold.

### per platform
| platform | truth_col | yaw_rmse | yaw_std | cte_rmse | n_seg |
|---|---|---|---|---|---|
| `FORD_F_150_LIGHTNING_MK1` | `yaw_rate_meas_rads` | 0.00608 | 0.00608 | 62.813 | 175 |
| `FORD_MUSTANG_MACH_E_MK1` | `yaw_rate_meas_rads` | 0.00905 | 0.00905 | 122.655 | 240 |
| `HYUNDAI_IONIQ_5` | `yaw_rate_meas_rads` | 0.00872 | 0.00872 | 106.907 | 800 |
| `TESLA_MODEL_3` | `psi_dot_rads` | 0.00000 | 0.00000 | 0.000 | 781 |

**Schema notes:**
- `TESLA_MODEL_3`: Tesla sim has no independent truth channel — psi_dot_rads IS the V0 KS output. Any deviation from V0 will *increase* RMSE on this platform. Treat near-zero Tesla RMSE as a sanity check, not a signal to optimise.

### per regime (yaw only)
- `straight`: rmse=0.00524, bias=+0.00005, n=4,318,457
- `steady`: rmse=0.00755, bias=-0.00023, n=707,241
- `transient`: rmse=0.01935, bias=-0.00039, n=167,934

### per-segment distribution
- **yaw_rate_rmse**: min=0, p25=0, median=0.003915, mean=0.0042314, p75=0.0070245, max=0.11507, std=0.0050899
- **cte_rmse**: min=0, p25=0, median=6.4216, mean=31.849, p75=40.115, max=421.15, std=56.652

### top 5 worst segments by CTE
| route/idx | platform | dist_m | cte_rmse | cte_signed | yaw_rmse |
|---|---|---|---|---|---|
| `00000217--5031f0026d/15` | `HYUNDAI_IONIQ_5` | 1639 | 421.15 | -279.94 | 0.02150 |
| `0000011a--bd8f19641a/3` | `HYUNDAI_IONIQ_5` | 1545 | 413.21 | -261.80 | 0.02120 |
| `00000000--33439c2a9c/13` | `FORD_MUSTANG_MACH_E_MK1` | 2022 | 367.13 | -274.52 | 0.01349 |
| `000000ea--9dd0e5fa19/24` | `HYUNDAI_IONIQ_5` | 1567 | 363.22 | -280.22 | 0.01530 |
| `00000130--1482cf04ed/11` | `HYUNDAI_IONIQ_5` | 1802 | 359.71 | -267.25 | 0.01386 |

### top 5 worst segments by yaw
| route/idx | platform | n_samp | yaw_rmse | yaw_bias |
|---|---|---|---|---|
| `000000cc--3d3da09ecd` `7` | `HYUNDAI_IONIQ_5` | 2548 | 0.11507 | -0.02641 |
| `00000000--baace6bb62` `1` | `FORD_MUSTANG_MACH_E_MK1` | 1720 | 0.06246 | +0.01866 |
| `00000011--8d0ad83de4` `18` | `FORD_MUSTANG_MACH_E_MK1` | 2899 | 0.03653 | +0.00049 |
| `0000000f--1eeaa129ce` `1` | `HYUNDAI_IONIQ_5` | 2899 | 0.02230 | +0.00455 |
| `00000009--95362b39f1` `1` | `FORD_MUSTANG_MACH_E_MK1` | 2899 | 0.02200 | -0.02157 |

### top 5 routes by CTE
| route | platform | n_seg | dist_m | yaw_rmse | cte_rmse | cte_signed |
|---|---|---|---|---|---|---|
| `00000217--5031f0026d` | `HYUNDAI_IONIQ_5` | 1 | 1639 | 0.02150 | 421.153 | -279.942 |
| `000000ea--9dd0e5fa19` | `HYUNDAI_IONIQ_5` | 1 | 1567 | 0.01530 | 363.221 | -280.218 |
| `00000130--1482cf04ed` | `HYUNDAI_IONIQ_5` | 1 | 1802 | 0.01386 | 359.709 | -267.255 |
| `00000000--33439c2a9c` | `FORD_MUSTANG_MACH_E_MK1` | 5 | 8287 | 0.01316 | 327.120 | -225.086 |
| `00000203--33080ebba2` | `HYUNDAI_IONIQ_5` | 1 | 1920 | 0.01580 | 315.539 | -222.227 |
