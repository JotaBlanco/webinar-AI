# Cohort canonical evaluation — 10 agents

- **idea**: `idea-01-lateral-attribution`
- **eval pool**: 130 held-out segments under `/Users/javiquix/Desktop/quixdev/F1/KB003/data/val-data`
- **V0 baselines**: yaw RMSE = **0.014563 rad/s** (318,760 samples); CTE RMSE = **147.4404 m** (117,650 bins)
- **reconstructed**: 10 ok / 0 failed (wall 3.82s, concurrency 8)

## Headline

- 🥇 **Best yaw**: `m1-agent-01` (+33.6%)
- 🥇 **Best CTE**: `m1-agent-02` (+34.6%)
- 🎯 **Winning both KPIs ≥ +30%** (1 agents): `m1-agent-02`

## Performance by family

Each family is a comparison group (e.g. `module-N`). Improvement %s computed against the SAME V0 baseline on the SAME held-out pool.

| family | n ok / total | yaw Δ% (mean ± σ) | CTE Δ% (mean ± σ) | failures |
|---|---|---|---|---|
| `module-1` | 10/10 | +30.5% ± 3.5% (med +31.2%) | +24.9% ± 4.6% (med +23.7%) | 0 |

## Per-platform breakdown

How each platform fared when supported. Mean across all agents that declared support AND ran successfully on that platform.

| platform | agents | yaw Δ% (mean ± σ) | CTE Δ% (mean ± σ) |
|---|---|---|---|
| `FORD_F_150_LIGHTNING_MK1` | 10 | +10.6% ± 3.6% (med +11.0%) | +53.4% ± 1.8% (med +53.6%) |
| `FORD_MUSTANG_MACH_E_MK1` | 10 | +46.8% ± 3.9% (med +46.8%) | +14.8% ± 6.2% (med +13.4%) |

## Per-agent canonical scorecard

| agent | family | status | yaw V0 | yaw final | yaw Δ% | CTE V0 | CTE final | CTE Δ% | n seg ok/total | wall |
|---|---|---|---|---|---|---|---|---|---|---|
| `m1-agent-01` | `module-1` | ok | 0.014563 | 0.009662 | **+33.6%** | 147.44 | 113.09 | **+23.3%** | 130/130 | 1.51s |
| `m1-agent-02` | `module-1` | ok | 0.014563 | 0.009855 | **+32.3%** | 147.44 | 96.40 | **+34.6%** | 130/130 | 1.51s |
| `m1-agent-03` | `module-1` | ok | 0.014563 | 0.010105 | **+30.6%** | 147.44 | 111.86 | **+24.1%** | 130/130 | 1.76s |
| `m1-agent-04` | `module-1` | ok | 0.014563 | 0.010244 | **+29.7%** | 147.44 | 113.11 | **+23.3%** | 130/130 | 1.51s |
| `m1-agent-05` | `module-1` | ok | 0.014563 | 0.010256 | **+29.6%** | 147.44 | 115.28 | **+21.8%** | 130/130 | 1.88s |
| `m1-agent-06` | `module-1` | ok | 0.014563 | 0.010181 | **+30.1%** | 147.44 | 109.33 | **+25.8%** | 130/130 | 1.51s |
| `m1-agent-07` | `module-1` | ok | 0.014563 | 0.009701 | **+33.4%** | 147.44 | 107.88 | **+26.8%** | 130/130 | 2.14s |
| `m1-agent-08` | `module-1` | ok | 0.014563 | 0.011518 | **+20.9%** | 147.44 | 113.56 | **+23.0%** | 130/130 | 2.03s |
| `m1-agent-09` | `module-1` | ok | 0.014563 | 0.009753 | **+33.0%** | 147.44 | 103.36 | **+29.9%** | 130/130 | 0.81s |
| `m1-agent-10` | `module-1` | ok | 0.014563 | 0.009936 | **+31.8%** | 147.44 | 123.15 | **+16.5%** | 130/130 | 2.05s |

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

## Reconstruction quality (substrate signal)

How many agents shipped the right artefacts to be canonically gradable. Failures here are a substrate / contract problem, not a model problem.

| format check | pass | fail |
|---|---|---|
| `agent_folder_exists` | 10 | 0 |
| `has_manifest_json` | 10 | 0 |
| `manifest_parsable` | 10 | 0 |
| `manifest_declares_predict_callable` | 10 | 0 |
| `manifest_declares_platform_support` | 10 | 0 |
| `has_predict_py` | 10 | 0 |
| `has_coeffs_json` | 9 | 1 |
| `has_report` | 0 | 10 |

## Worst-of-cohort (among ok submissions)

**Lowest yaw Δ%**:
- `m1-agent-08` (+20.9%)
- `m1-agent-05` (+29.6%)
- `m1-agent-04` (+29.7%)

**Lowest CTE Δ%**:
- `m1-agent-10` (+16.5%)
- `m1-agent-05` (+21.8%)
- `m1-agent-08` (+23.0%)
