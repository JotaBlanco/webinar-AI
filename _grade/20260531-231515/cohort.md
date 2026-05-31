# Cohort canonical evaluation — 20 agents

- **idea**: `idea-01-lateral-attribution`
- **eval pool**: 130 held-out segments under `/Users/javiquix/Desktop/quixdev/F1/KB003/data/val-data`
- **V0 baselines**: yaw RMSE = **0.014563 rad/s** (318,760 samples); CTE RMSE = **147.4404 m** (117,650 bins)
- **reconstructed**: 20 ok / 0 failed (wall 3.61s, concurrency 8)

## Headline

- 🥇 **Best yaw**: `m1-agent-01` (+33.6%)
- 🥇 **Best CTE**: `m1-agent-02` (+34.6%)
- 🎯 **Winning both KPIs ≥ +30%** (1 agents): `m1-agent-02`

## Performance by family

Each family is a comparison group (e.g. `module-N`). Improvement %s computed against the SAME V0 baseline on the SAME held-out pool.

| family | n ok / total | yaw Δ% (mean ± σ) | CTE Δ% (mean ± σ) | failures |
|---|---|---|---|---|
| `module-1` | 10/10 | +30.5% ± 3.5% (med +31.2%) | +24.9% ± 4.6% (med +23.7%) | 0 |
| `module-2` | 10/10 | +30.4% ± 3.3% (med +31.0%) | +21.8% ± 6.7% (med +24.2%) | 0 |

## Per-platform breakdown

How each platform fared when supported. Mean across all agents that declared support AND ran successfully on that platform.

| platform | agents | yaw Δ% (mean ± σ) | CTE Δ% (mean ± σ) |
|---|---|---|---|
| `FORD_F_150_LIGHTNING_MK1` | 20 | +11.1% ± 2.8% (med +11.1%) | +53.7% ± 1.7% (med +53.9%) |
| `FORD_MUSTANG_MACH_E_MK1` | 20 | +46.3% ± 4.7% (med +46.8%) | +12.7% ± 7.9% (med +13.9%) |

## Per-agent canonical scorecard

| agent | family | status | yaw V0 | yaw final | yaw Δ% | CTE V0 | CTE final | CTE Δ% | n seg ok/total | wall |
|---|---|---|---|---|---|---|---|---|---|---|
| `m1-agent-01` | `module-1` | ok | 0.014563 | 0.009662 | **+33.6%** | 147.44 | 113.09 | **+23.3%** | 130/130 | 1.18s |
| `m1-agent-02` | `module-1` | ok | 0.014563 | 0.009855 | **+32.3%** | 147.44 | 96.40 | **+34.6%** | 130/130 | 1.18s |
| `m1-agent-03` | `module-1` | ok | 0.014563 | 0.010105 | **+30.6%** | 147.44 | 111.86 | **+24.1%** | 130/130 | 1.43s |
| `m1-agent-04` | `module-1` | ok | 0.014563 | 0.010244 | **+29.7%** | 147.44 | 113.11 | **+23.3%** | 130/130 | 1.18s |
| `m1-agent-05` | `module-1` | ok | 0.014563 | 0.010256 | **+29.6%** | 147.44 | 115.28 | **+21.8%** | 130/130 | 1.55s |
| `m1-agent-06` | `module-1` | ok | 0.014563 | 0.010181 | **+30.1%** | 147.44 | 109.33 | **+25.8%** | 130/130 | 1.18s |
| `m1-agent-07` | `module-1` | ok | 0.014563 | 0.009701 | **+33.4%** | 147.44 | 107.88 | **+26.8%** | 130/130 | 1.85s |
| `m1-agent-08` | `module-1` | ok | 0.014563 | 0.011518 | **+20.9%** | 147.44 | 113.56 | **+23.0%** | 130/130 | 1.72s |
| `m1-agent-09` | `module-1` | ok | 0.014563 | 0.009753 | **+33.0%** | 147.44 | 103.36 | **+29.9%** | 130/130 | 0.89s |
| `m1-agent-10` | `module-1` | ok | 0.014563 | 0.009936 | **+31.8%** | 147.44 | 123.15 | **+16.5%** | 130/130 | 2.19s |
| `m2-agent-01` | `module-2` | ok | 0.014563 | 0.010049 | **+31.0%** | 147.44 | 108.77 | **+26.2%** | 130/130 | 0.79s |
| `m2-agent-02` | `module-2` | ok | 0.014563 | 0.010010 | **+31.3%** | 147.44 | 106.11 | **+28.0%** | 130/130 | 0.79s |
| `m2-agent-03` | `module-2` | ok | 0.014563 | 0.010104 | **+30.6%** | 147.44 | 111.85 | **+24.1%** | 130/130 | 0.81s |
| `m2-agent-04` | `module-2` | ok | 0.014563 | 0.011514 | **+20.9%** | 147.44 | 141.71 | **+3.9%** | 130/130 | 1.29s |
| `m2-agent-05` | `module-2` | ok | 0.014563 | 0.009714 | **+33.3%** | 147.44 | 113.68 | **+22.9%** | 130/130 | 0.79s |
| `m2-agent-06` | `module-2` | ok | 0.014563 | 0.010189 | **+30.0%** | 147.44 | 116.48 | **+21.0%** | 130/130 | 0.79s |
| `m2-agent-07` | `module-2` | ok | 0.014563 | 0.009925 | **+31.8%** | 147.44 | 123.02 | **+16.6%** | 130/130 | 0.87s |
| `m2-agent-08` | `module-2` | ok | 0.014563 | 0.009788 | **+32.8%** | 147.44 | 111.80 | **+24.2%** | 130/130 | 0.85s |
| `m2-agent-09` | `module-2` | ok | 0.014563 | 0.010082 | **+30.8%** | 147.44 | 111.16 | **+24.6%** | 130/130 | 0.76s |
| `m2-agent-10` | `module-2` | ok | 0.014563 | 0.010041 | **+31.0%** | 147.44 | 108.70 | **+26.3%** | 130/130 | 0.76s |

## Per-segment yaw-RMSE distribution (spread within each agent)

Pooled RMSE can hide that an agent is great on most segments but pathological on a few. These columns expose that.

| agent | n segs | min | median | mean | max | std |
|---|---|---|---|---|---|---|
| `m1-agent-01` | 125 | 0.0023 | 0.0060 | 0.0116 | 0.6342 | 0.0560 |
| `m1-agent-02` | 125 | 0.0025 | 0.0066 | 0.0118 | 0.6384 | 0.0563 |
| `m1-agent-03` | 125 | 0.0026 | 0.0069 | 0.0122 | 0.6394 | 0.0564 |
| `m1-agent-04` | 125 | 0.0025 | 0.0070 | 0.0124 | 0.6552 | 0.0578 |
| `m1-agent-05` | 125 | 0.0024 | 0.0069 | 0.0124 | 0.6536 | 0.0576 |
| `m1-agent-06` | 125 | 0.0024 | 0.0072 | 0.0123 | 0.6336 | 0.0559 |
| `m1-agent-07` | 125 | 0.0022 | 0.0064 | 0.0116 | 0.6383 | 0.0563 |
| `m1-agent-08` | 125 | 0.0030 | 0.0084 | 0.0139 | 0.6339 | 0.0558 |
| `m1-agent-09` | 125 | 0.0020 | 0.0064 | 0.0116 | 0.6314 | 0.0557 |
| `m1-agent-10` | 125 | 0.0024 | 0.0062 | 0.0119 | 0.6368 | 0.0562 |
| `m2-agent-01` | 125 | 0.0029 | 0.0071 | 0.0121 | 0.6366 | 0.0561 |
| `m2-agent-02` | 125 | 0.0026 | 0.0070 | 0.0121 | 0.6388 | 0.0563 |
| `m2-agent-03` | 125 | 0.0026 | 0.0069 | 0.0122 | 0.6394 | 0.0564 |
| `m2-agent-04` | 125 | 0.0024 | 0.0080 | 0.0140 | 0.6595 | 0.0582 |
| `m2-agent-05` | 125 | 0.0024 | 0.0058 | 0.0115 | 0.6609 | 0.0584 |
| `m2-agent-06` | 125 | 0.0028 | 0.0068 | 0.0124 | 0.6408 | 0.0565 |
| `m2-agent-07` | 125 | 0.0024 | 0.0062 | 0.0119 | 0.6349 | 0.0560 |
| `m2-agent-08` | 125 | 0.0025 | 0.0064 | 0.0118 | 0.6383 | 0.0563 |
| `m2-agent-09` | 125 | 0.0026 | 0.0071 | 0.0122 | 0.6357 | 0.0561 |
| `m2-agent-10` | 125 | 0.0025 | 0.0068 | 0.0120 | 0.6592 | 0.0582 |

## Calibration cards (agent-reported coefficients)

Where the cohort converges on similar physics vs where it forks. Flattened from each agent's `coeffs.json`.

### `m1-agent-02`
```json
{
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.4760851016953556,
    "K_us": 0.0026722138032651867,
    "bias_rad": 0.0002686192499419401
  },
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.809760457416018,
    "K_us": 0.0038412171248315657,
    "bias_rad": 0.001307379955568698
  },
  "HYUNDAI_IONIQ_5": {
    "L": 3.096229822470566,
    "K_us": 0.003695564361835472,
    "bias_rad": -0.0002960976826300522
  },
  "TESLA_MODEL_3": {
    "L": 2.875,
    "K_us": 0.0,
    "bias_rad": 0.0
  }
}
```

### `m1-agent-03`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.7,
    "a": 0.97434,
    "b": -0.001229,
    "K": 0.003837
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.984,
    "a": 1.199892,
    "b": 3.4e-05,
    "K": 0.002874
  },
  "HYUNDAI_IONIQ_5": {
    "L": 3.0,
    "a": 0.970713,
    "b": 0.000507,
    "K": 0.003386
  },
  "TESLA_MODEL_3": {
    "L": 2.875,
    "a": 1.01741,
    "b": 5e-06,
    "K": 6.7e-05
  }
}
```

### `m1-agent-04`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "a": -0.004329037631466362,
    "b": 0.9177897626357783,
    "c": -0.00044178131403551616
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "a": 0.0002206757945255914,
    "b": 1.1513559927303039,
    "c": -0.0005583363495612761
  },
  "HYUNDAI_IONIQ_5": {
    "a": 0.0020222989265629857,
    "b": 0.9120045284217976,
    "c": -0.00048449411444108955
  },
  "TESLA_MODEL_3": {
    "a": 0.0002206757945255914,
    "b": 1.1513559927303039,
    "c": -0.0005583363495612761
  },
  "_default": {
    "a": 0.0,
    "b": 1.0,
    "c": 0.0
  }
}
```

### `m1-agent-05`
```json
{
  "model": "V2b: yaw = (v/L) * tan(k*(delta - b)) / (1 + Ku*v^2); trajectory from yaw integration",
  "platforms": {
    "TESLA_MODEL_3": {
      "L": 2.875,
      "b": 0.0011,
      "Ku": 0.000861,
      "k": 0.95419,
      "fit_source": "wheel-speed-derived yaw proxy (FL+RL vs FR+RR over track=1.580m)"
    },
    "FORD_MUSTANG_MACH_E_MK1": {
      "L": 2.984,
      "b": -3.46e-05,
      "Ku": 0.000742,
      "k": 1.14486,
      "fit_source": "yaw_rate_meas_rads"
    },
    "FORD_F_150_LIGHTNING_MK1": {
      "L": 3.7,
      "b": 0.001203,
      "Ku": 0.000787,
      "k": 0.92218,
      "fit_source": "yaw_rate_meas_rads"
    },
    "HYUNDAI_IONIQ_5": {
      "L": 3.0,
      "b": -0.000525,
      "Ku": 0.000958,
      "k": 0.94102,
      "fit_source": "yaw_rate_meas_rads"
    }
  },
  "default": {
    "L": 3.0,
    "b": 0.0,
    "Ku": 0.001,
    "k": 1.0
  }
}
```

### `m1-agent-06`
```json
{
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.984,
    "best": "M2_understeer",
    "m1": {
      "a": 1.0870612234849137
    },
    "m2": {
      "L_eff": 2.4763030468069056,
      "K_us": 0.0024395167795073017
    },
    "m3": {
      "a": 0.9751496691433119,
      "b": 0.23839497273290036,
      "c": 0.0004082870644824788
    },
    "val_rmse": {
      "V0": 0.0267999381028469,
      "M1": 0.027439581036525294,
      "M2": 0.026420879339395156,
      "M3": 0.031903168689021696
    },
    "train_rmse": {
      "V0": 0.012685628695945105,
      "M1": 0.011389013310887795,
      "M2": 0.008745921115146504,
      "M3": 0.010386863485176999
    }
  },
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.7,
    "best": "M2_understeer",
    "m1": {
      "a": 0.8569324797501493
    },
    "m2": {
      "L_eff": 3.882198880475702,
      "K_us": 0.003439279945738158
    },
    "m3": {
      "a": 0.8772240685582882,
      "b": -0.031353830652592465,
      "c": -0.0036354381262862774
    },
    "val_rmse": {
      "V0": 0.01591104278075153,
      "M1": 0.011141896721881754,
      "M2": 0.0073696198273352906,
      "M3": 0.0104650790814036
    },
    "train_rmse": {
      "V0": 0.02018452928972004,
   
```

### `m1-agent-07`
```json
{
  "TESLA_MODEL_3": {
    "L": 2.875,
    "K": 5.976739689434123e-05,
    "gain": 1.016627098141411,
    "tau": 0.0002453976193050897,
    "K_us_only": 5.976415408617292e-05,
    "gain_us_only": 1.016626972603616,
    "variant": "V0_KS"
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.984,
    "K": 0.0030813193405498413,
    "gain": 1.203625810479946,
    "tau": 0.07613854815855436,
    "K_us_only": 0.003102861140280794,
    "gain_us_only": 1.2081544371095503,
    "variant": "V2_ust_lag"
  },
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.7,
    "K": 0.0036205053672292075,
    "gain": 0.9682946246028614,
    "tau": 0.06656923952903109,
    "K_us_only": 0.0036226603427926504,
    "gain_us_only": 0.9715000932503463,
    "variant": "V2_ust_lag"
  },
  "HYUNDAI_IONIQ_5": {
    "L": 3.0,
    "K": 0.0036584318819639816,
    "gain": 0.9713926728919929,
    "tau": 0.06316742896949837,
    "K_us_only": 0.0036420764870417712,
    "gain_us_only": 0.9733017895355937,
    "variant": "V2_ust_lag"
  }
}
```

### `m1-agent-08`
```json
{
  "HYUNDAI_IONIQ_5": {
    "L": 3.0,
    "K": 0.0033895612010179177,
    "s": 0.9668278221152291,
    "off": 0.0005045046778856075,
    "lag": 3,
    "rmse": 0.00888482422851739
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.984,
    "K": 0.002625595512351926,
    "s": 1.1771921499482927,
    "off": 3.9923690213217876e-05,
    "lag": 4,
    "rmse": 0.01315660341959157
  },
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.7,
    "K": 0.0035388455508032707,
    "s": 0.9569361755429138,
    "off": -0.0011908292677060655,
    "lag": 3,
    "rmse": 0.011832340064259452
  },
  "TESLA_MODEL_3": {
    "L": 2.875,
    "K": 0.0033895612010179177,
    "s": 1.0,
    "off": 0.0,
    "lag": 3,
    "rmse": null
  }
}
```

### `m1-agent-09`
```json
{
  "HYUNDAI_IONIQ_5": {
    "L": 3.0917809316280884,
    "K": 0.0035402653043422943,
    "tau": 0.04920512646161311,
    "bias": 0.0010739596129365433,
    "rmse_train_subset": 0.007106525166586293,
    "rmse_v0_train_subset": 0.015720113517713782,
    "n_train_segments": 80,
    "stride": 4
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.4089997702377928,
    "K": 0.003112009278931996,
    "tau": 0.07824623486733845,
    "bias": -0.0002872245794345976,
    "rmse_train_subset": 0.00801650885611504,
    "rmse_v0_train_subset": 0.011641820559265024,
    "n_train_segments": 80,
    "stride": 4
  },
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.832567695729642,
    "K": 0.003764095251877052,
    "tau": 0.056758211461132996,
    "bias": -0.005505959949168079,
    "rmse_train_subset": 0.013260238845035393,
    "rmse_v0_train_subset": 0.021144038083265617,
    "n_train_segments": 80,
    "stride": 4
  },
  "TESLA_MODEL_3": {
    "L": 2.875,
    "K": 0.0,
    "tau": 0.0,
    "bias": 0.0,
    "use_v0": true,
    "note": "No yaw_rate_meas channel in Tesla sim CSV \u2014 falls back to V0 KS (yaw_rate_pred_rads from sim_df)."
  }
}
```

### `m1-agent-10`
```json
{
  "FORD_MUSTANG_MACH_E_MK1": {
    "L_eff": 2.5297190644305063,
    "K_us": 0.0015446536838391765,
    "d0": -4.756112262525493e-05,
    "tau_yaw": 0.02,
    "tau_steer": 0.05
  },
  "FORD_F_150_LIGHTNING_MK1": {
    "L_eff": 3.834827559665228,
    "K_us": 0.0031524889056087045,
    "d0": 0.00115199881391885,
    "tau_yaw": 0.0,
    "tau_steer": 0.05
  },
  "HYUNDAI_IONIQ_5": {
    "L_eff": 3.1485752690608293,
    "K_us": 0.0021732037046845788,
    "d0": -0.0005619614330402095,
    "tau_yaw": 0.0,
    "tau_steer": 0.05
  },
  "TESLA_MODEL_3": {
    "_note": "no truth available \u2014 passthrough yaw_rate_pred_rads (V0 KS)",
    "passthrough": true
  }
}
```

### `m2-agent-01`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.7,
    "K": 0.004000000000000001,
    "gain": 0.977434717343858,
    "bias": -0.004397919939528653,
    "train_n": 394138,
    "dev_n": 36852,
    "train_rmse": 0.0063997732172507244,
    "dev_rmse": 0.005370969758349156,
    "dev_v0_rmse": 0.014520627147082686
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.984,
    "K": 0.003,
    "gain": 1.2098678599814878,
    "bias": 4.346115259283436e-07,
    "train_n": 479250,
    "dev_n": 135925,
    "train_rmse": 0.009663710508613893,
    "dev_rmse": 0.009031858354136913,
    "dev_v0_rmse": 0.011972817404522829
  },
  "HYUNDAI_IONIQ_5": {
    "L": 2.9,
    "K": 0.0035000000000000005,
    "gain": 0.9432997032403692,
    "bias": 0.001941986334044768,
    "train_n": 1617812,
    "dev_n": 424458,
    "train_rmse": 0.007756956209526051,
    "dev_rmse": 0.011813187964464438,
    "dev_v0_rmse": 0.021906885777351892
  },
  "TESLA_MODEL_3": {
    "L": 2.875,
    "K": 0.0,
    "gain": 1.0,
    "bias": 0.0,
    "passthrough": true,
    "note": "Tesla sim/ has no ground-truth yaw rate (psi_dot_rads is the V0 output itself). Use V0 KS formula as predict."
  }
}
```

### `m2-agent-03`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "platform": "FORD_F_150_LIGHTNING_MK1",
    "L": 3.7,
    "n_samples": 430990,
    "rmse_v0": 0.016327157090019005,
    "rmse_v1": 0.007867193883977044,
    "K_v1": 0.0043769531249999985,
    "rmse_v2": 0.00640773025816659,
    "K_v2": 0.003836687017912508,
    "a_v2": 0.9743406550510199,
    "b_v2": -0.001228592917784131
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "platform": "FORD_MUSTANG_MACH_E_MK1",
    "L": 2.984,
    "n_samples": 615175,
    "rmse_v0": 0.013616820108542612,
    "rmse_v1": 0.013930807470187448,
    "K_v1": 0.000785400390624989,
    "rmse_v2": 0.0095149036095479,
    "K_v2": 0.0028742800060782272,
    "a_v2": 1.1998919734409932,
    "b_v2": 3.385609342398125e-05
  },
  "HYUNDAI_IONIQ_5": {
    "platform": "HYUNDAI_IONIQ_5",
    "L": 3.0,
    "n_samples": 2042270,
    "rmse_v0": 0.017084454875116246,
    "rmse_v1": 0.009100616867655459,
    "K_v1": 0.0042265624999999985,
    "rmse_v2": 0.008741269113389604,
    "K_v2": 0.0033859035164445724,
    "a_v2": 0.9707125684779052,
    "b_v2": 0.0005066770839987745
  }
}
```

### `m2-agent-05`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "K_us": 0.003252042935582439,
    "scale": 0.930791075174131,
    "delta_bias": -0.0012579889549048536,
    "tau": -0.06166529191632345,
    "alpha3": 0.3621598970166438,
    "L0": 3.7,
    "rmse_fit": 0.005286746499014517,
    "n_samples": 430990
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "K_us": 0.002277151306995263,
    "scale": 1.139240298647753,
    "delta_bias": 2.4506348721266604e-05,
    "tau": -0.06954742575619027,
    "alpha3": 0.8230046570913112,
    "L0": 2.984,
    "rmse_fit": 0.008302414265795428,
    "n_samples": 615175
  },
  "HYUNDAI_IONIQ_5": {
    "K_us": 0.003004507625096826,
    "scale": 0.9428309430330226,
    "delta_bias": 0.0005222810160951011,
    "tau": -0.055061886879326435,
    "alpha3": 0.3111971519866422,
    "L0": 3.0,
    "rmse_fit": 0.008141797524667264,
    "n_samples": 2042270
  },
  "TESLA_MODEL_3": {
    "K_us": 0.002277151306995263,
    "scale": 1.0,
    "delta_bias": 0.0,
    "tau": -0.06954742575619027,
    "alpha3": 0.0,
    "L0": 2.875
  }
}
```

### `m2-agent-07`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "tau": 0.05,
    "L_eff": 3.8588781722695416,
    "K_u": 0.00314039574481963,
    "delta_bias_rad": -0.001157331673169034,
    "rmse": 0.005592721659455879
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "tau": 0.08,
    "L_eff": 2.5486304264900417,
    "K_u": 0.0015312706121448161,
    "delta_bias_rad": 4.8217638587095315e-05,
    "rmse": 0.008347407485517062
  },
  "HYUNDAI_IONIQ_5": {
    "tau": 0.05,
    "L_eff": 3.163750474852756,
    "K_u": 0.0021607848879418314,
    "delta_bias_rad": 0.0005617097326308059,
    "rmse": 0.007713638558960502
  }
}
```

### `m2-agent-10`
```json
{
  "coeffs": {
    "TESLA_MODEL_3": {
      "L": 2.874999668129361,
      "K": -2.282682116433651e-10,
      "delta0": 1.1156258287249449e-11,
      "gain": 0.9999998878224541
    },
    "HYUNDAI_IONIQ_5": {
      "L": 2.9152145202323267,
      "K": 0.002907166003831828,
      "delta0": 0.0004374734203757065,
      "gain": 0.9231310287342123
    },
    "FORD_F_150_LIGHTNING_MK1": {
      "L": 3.5294882240304677,
      "K": 0.0031783930792072855,
      "delta0": -0.001053480864687961,
      "gain": 0.8999290931005035
    },
    "FORD_MUSTANG_MACH_E_MK1": {
      "L": 3.5439010986209483,
      "K": 0.002856809241613734,
      "delta0": -7.107942739837021e-05,
      "gain": 1.3706447622641043
    }
  },
  "dev_score": {
    "yaw_rmse": 0.00858692600976206,
    "cte_rmse": 75.63162535104003,
    "per_platform": {
      "FORD_F_150_LIGHTNING_MK1": {
        "yaw_rmse": 0.006129934856592167,
        "cte_rmse": 54.15933790655657
      },
      "FORD_MUSTANG_MACH_E_MK1": {
        "yaw_rmse": 0.008203487066310178,
        "cte_rmse": 90.705721951431
      },
      "HYUNDAI_IONIQ_5": {
        "yaw_rmse": 0.012205543094350927,
        "cte_rmse": 108.97445639625865
      },
      "TESLA_M
```

## Reconstruction quality (substrate signal)

How many agents shipped the right artefacts to be canonically gradable. Failures here are a substrate / contract problem, not a model problem.

| format check | pass | fail |
|---|---|---|
| `agent_folder_exists` | 20 | 0 |
| `has_manifest_json` | 20 | 0 |
| `manifest_parsable` | 20 | 0 |
| `manifest_declares_predict_callable` | 20 | 0 |
| `manifest_declares_platform_support` | 20 | 0 |
| `has_predict_py` | 20 | 0 |
| `has_coeffs_json` | 14 | 6 |
| `has_report` | 3 | 17 |

## Worst-of-cohort (among ok submissions)

**Lowest yaw Δ%**:
- `m1-agent-08` (+20.9%)
- `m2-agent-04` (+20.9%)
- `m1-agent-05` (+29.6%)

**Lowest CTE Δ%**:
- `m2-agent-04` (+3.9%)
- `m1-agent-10` (+16.5%)
- `m2-agent-07` (+16.6%)
