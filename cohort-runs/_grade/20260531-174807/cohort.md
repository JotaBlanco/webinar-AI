# Cohort canonical evaluation — 29 agents

- **idea**: `idea-01-lateral-attribution`
- **eval pool**: 130 held-out segments under `/Users/javiquix/Desktop/quixdev/F1/KB003/data/val-data`
- **V0 baselines**: yaw RMSE = **0.014563 rad/s** (318,760 samples); CTE RMSE = **147.4404 m** (117,650 bins)
- **reconstructed**: 28 ok / 1 failed (wall 4.37s, concurrency 8)

## Headline

- 🥇 **Best yaw**: `m3-agent-09` (+38.6%)
- 🥇 **Best CTE**: `m1-agent-06` (+78.8%)
- 🎯 **Winning both KPIs ≥ +30%** (5 agents): `m3-agent-09`, `m3-agent-06`, `m3-agent-02`, `m3-agent-10`, `m2-agent-04`

## Performance by family

Each family is a comparison group (e.g. `module-N`). Improvement %s computed against the SAME V0 baseline on the SAME held-out pool.

| family | n ok / total | yaw Δ% (mean ± σ) | CTE Δ% (mean ± σ) | failures |
|---|---|---|---|---|
| `module-1` | 8/9 | +25.2% ± 8.8% (med +29.6%) | +30.2% ± 18.4% (med +24.1%) | 1 |
| `module-2` | 10/10 | +31.8% ± 4.4% (med +33.3%) | +24.3% ± 4.6% (med +24.7%) | 0 |
| `module-3` | 10/10 | +34.8% ± 2.2% (med +34.0%) | +32.8% ± 12.7% (med +29.0%) | 0 |

## Per-platform breakdown

How each platform fared when supported. Mean across all agents that declared support AND ran successfully on that platform.

| platform | agents | yaw Δ% (mean ± σ) | CTE Δ% (mean ± σ) |
|---|---|---|---|
| `FORD_F_150_LIGHTNING_MK1` | 28 | +11.3% ± 5.2% (med +13.1%) | +54.6% ± 4.3% (med +54.0%) |
| `FORD_MUSTANG_MACH_E_MK1` | 28 | +47.5% ± 10.0% (med +49.4%) | +20.0% ± 17.3% (med +13.9%) |

## Per-agent canonical scorecard

| agent | family | status | yaw Δ% | CTE Δ% | claimed yaw | claimed CTE | yaw gap | CTE gap | n seg | wall |
|---|---|---|---|---|---|---|---|---|---|---|
| `m1-agent-01` | `module-1` | ok | **+33.6%** | **+23.1%** | +33.7% | +60.0% | +0.1% | +36.9% | 130/130 | 2.14s |
| `m1-agent-02` | `module-1` | ok | **+32.6%** | **+24.5%** | +55.0% | +52.0% | +22.4% | +27.5% | 130/130 | 1.28s |
| `m1-agent-03` | `module-1` | ok | **+28.9%** | **+20.0%** | — | — | — | — | 130/130 | 1.73s |
| `m1-agent-04` | `module-1` | ok | **+33.0%** | **+24.5%** | +64.8% | +70.7% | +31.8% | +46.2% | 130/130 | 1.71s |
| `m1-agent-05` | `module-1` | ok | **+30.2%** | **+22.7%** | +27.3% | +19.9% | -2.9% | -2.8% | 130/130 | 1.28s |
| `m1-agent-06` | `module-1` | ok | **+19.9%** | **+78.8%** | — | — | — | — | 130/130 | 1.28s |
| `m1-agent-07` | `module-1` | ❌ **import_failed** | — | — | — | — | — | — | 0/0 | — |
| `m1-agent-09` | `module-1` | ok | **+12.3%** | **+24.0%** | — | — | — | — | 130/130 | 1.83s |
| `m1-agent-10` | `module-1` | ok | **+10.9%** | **+24.1%** | — | — | — | — | 130/130 | 0.57s |
| `m2-agent-01` | `module-2` | ok | **+18.6%** | **+15.1%** | +24.8% | +29.6% | +6.2% | +14.5% | 130/130 | 0.74s |
| `m2-agent-02` | `module-2` | ok | **+33.3%** | **+24.3%** | +47.5% | +33.0% | +14.2% | +8.7% | 130/130 | 0.67s |
| `m2-agent-03` | `module-2` | ok | **+33.7%** | **+26.6%** | +47.0% | +33.0% | +13.3% | +6.4% | 130/130 | 0.68s |
| `m2-agent-04` | `module-2` | ok | **+33.5%** | **+33.2%** | +50.0% | +36.0% | +16.5% | +2.8% | 130/130 | 0.7s |
| `m2-agent-05` | `module-2` | ok | **+31.8%** | **+18.4%** | +34.9% | +28.5% | +3.1% | +10.1% | 130/130 | 0.72s |
| `m2-agent-06` | `module-2` | ok | **+33.5%** | **+25.1%** | +51.0% | +33.0% | +17.5% | +7.9% | 130/130 | 0.76s |
| `m2-agent-07` | `module-2` | ok | **+32.8%** | **+26.8%** | +44.2% | +22.7% | +11.4% | -4.1% | 130/130 | 0.68s |
| `m2-agent-08` | `module-2` | ok | **+33.4%** | **+24.5%** | +44.5% | +22.6% | +11.1% | -1.9% | 130/130 | 0.58s |
| `m2-agent-09` | `module-2` | ok | **+33.3%** | **+24.8%** | +47.7% | +32.8% | +14.4% | +8.0% | 130/130 | 1.67s |
| `m2-agent-10` | `module-2` | ok | **+33.7%** | **+24.1%** | +48.0% | +33.0% | +14.3% | +8.9% | 130/130 | 0.68s |
| `m3-agent-01` | `module-3` | ok | **+33.9%** | **+29.8%** | +45.8% | +30.6% | +11.9% | +0.8% | 130/130 | 1.33s |
| `m3-agent-02` | `module-3` | ok | **+37.2%** | **+50.2%** | +46.1% | +28.1% | +8.9% | -22.1% | 130/130 | 0.71s |
| `m3-agent-03` | `module-3` | ok | **+33.3%** | **+22.0%** | +51.0% | +33.0% | +17.7% | +11.0% | 130/130 | 0.68s |
| `m3-agent-04` | `module-3` | ok | **+32.7%** | **+20.3%** | +51.0% | +33.0% | +18.3% | +12.7% | 130/130 | 0.72s |
| `m3-agent-05` | `module-3` | ok | **+32.2%** | **+19.2%** | +47.0% | +33.0% | +14.8% | +13.8% | 130/130 | 0.69s |
| `m3-agent-06` | `module-3` | ok | **+38.3%** | **+51.9%** | +49.8% | +41.4% | +11.5% | -10.5% | 130/130 | 0.75s |
| `m3-agent-07` | `module-3` | ok | **+34.1%** | **+28.3%** | +47.0% | +32.0% | +12.9% | +3.7% | 130/130 | 0.69s |
| `m3-agent-08` | `module-3` | ok | **+33.0%** | **+22.8%** | +51.0% | +33.0% | +18.0% | +10.2% | 130/130 | 0.73s |
| `m3-agent-09` | `module-3` | ok | **+38.6%** | **+51.8%** | +45.0% | +47.0% | +6.4% | -4.8% | 130/130 | 0.72s |
| `m3-agent-10` | `module-3` | ok | **+34.8%** | **+31.4%** | +55.0% | +28.0% | +20.2% | -3.4% | 130/130 | 0.69s |

## Self-awareness diagnostic — claimed vs canonical Δ%

Gap = claimed − canonical. Positive gap = over-claim; negative gap = under-claim.

| agent | family | claimed yaw | canonical yaw | yaw gap | claimed CTE | canonical CTE | CTE gap | notes |
|---|---|---|---|---|---|---|---|---|
| `m1-agent-01` | `module-1` | +33.7% | +33.6% | +0.1% | +60.0% | +23.1% | +36.9% |  |
| `m1-agent-02` | `module-1` | +55.0% | +32.6% | +22.4% | +52.0% | +24.5% | +27.5% |  |
| `m1-agent-03` | `module-1` | — | +28.9% | — | — | +20.0% | — | no quantitative claim |
| `m1-agent-04` | `module-1` | +64.8% | +33.0% | +31.8% | +70.7% | +24.5% | +46.2% |  |
| `m1-agent-05` | `module-1` | +27.3% | +30.2% | -2.9% | +19.9% | +22.7% | -2.8% |  |
| `m1-agent-06` | `module-1` | — | +19.9% | — | — | +78.8% | — | no quantitative claim |
| `m1-agent-09` | `module-1` | — | +12.3% | — | — | +24.0% | — | no quantitative claim |
| `m1-agent-10` | `module-1` | — | +10.9% | — | — | +24.1% | — | no quantitative claim |
| `m2-agent-01` | `module-2` | +24.8% | +18.6% | +6.2% | +29.6% | +15.1% | +14.5% |  |
| `m2-agent-02` | `module-2` | +47.5% | +33.3% | +14.2% | +33.0% | +24.3% | +8.7% |  |
| `m2-agent-03` | `module-2` | +47.0% | +33.7% | +13.3% | +33.0% | +26.6% | +6.4% |  |
| `m2-agent-04` | `module-2` | +50.0% | +33.5% | +16.5% | +36.0% | +33.2% | +2.8% |  |
| `m2-agent-05` | `module-2` | +34.9% | +31.8% | +3.1% | +28.5% | +18.4% | +10.1% |  |
| `m2-agent-06` | `module-2` | +51.0% | +33.5% | +17.5% | +33.0% | +25.1% | +7.9% |  |
| `m2-agent-07` | `module-2` | +44.2% | +32.8% | +11.4% | +22.7% | +26.8% | -4.1% |  |
| `m2-agent-08` | `module-2` | +44.5% | +33.4% | +11.1% | +22.6% | +24.5% | -1.9% |  |
| `m2-agent-09` | `module-2` | +47.7% | +33.3% | +14.4% | +32.8% | +24.8% | +8.0% |  |
| `m2-agent-10` | `module-2` | +48.0% | +33.7% | +14.3% | +33.0% | +24.1% | +8.9% |  |
| `m3-agent-01` | `module-3` | +45.8% | +33.9% | +11.9% | +30.6% | +29.8% | +0.8% |  |
| `m3-agent-02` | `module-3` | +46.1% | +37.2% | +8.9% | +28.1% | +50.2% | -22.1% |  |
| `m3-agent-03` | `module-3` | +51.0% | +33.3% | +17.7% | +33.0% | +22.0% | +11.0% |  |
| `m3-agent-04` | `module-3` | +51.0% | +32.7% | +18.3% | +33.0% | +20.3% | +12.7% |  |
| `m3-agent-05` | `module-3` | +47.0% | +32.2% | +14.8% | +33.0% | +19.2% | +13.8% |  |
| `m3-agent-06` | `module-3` | +49.8% | +38.3% | +11.5% | +41.4% | +51.9% | -10.5% |  |
| `m3-agent-07` | `module-3` | +47.0% | +34.1% | +12.9% | +32.0% | +28.3% | +3.7% |  |
| `m3-agent-08` | `module-3` | +51.0% | +33.0% | +18.0% | +33.0% | +22.8% | +10.2% |  |
| `m3-agent-09` | `module-3` | +45.0% | +38.6% | +6.4% | +47.0% | +51.8% | -4.8% |  |
| `m3-agent-10` | `module-3` | +55.0% | +34.8% | +20.2% | +28.0% | +31.4% | -3.4% |  |

## Per-segment yaw-RMSE distribution (spread within each agent)

Pooled RMSE can hide that an agent is great on most segments but pathological on a few. These columns expose that.

| agent | n segs | min | median | mean | max | std |
|---|---|---|---|---|---|---|
| `m1-agent-01` | 125 | 0.0024 | 0.0058 | 0.0116 | 0.6373 | 0.0563 |
| `m1-agent-02` | 125 | 0.0022 | 0.0063 | 0.0117 | 0.6294 | 0.0555 |
| `m1-agent-03` | 125 | 0.0024 | 0.0073 | 0.0125 | 0.6575 | 0.0580 |
| `m1-agent-04` | 125 | 0.0022 | 0.0060 | 0.0117 | 0.6566 | 0.0580 |
| `m1-agent-05` | 125 | 0.0024 | 0.0069 | 0.0123 | 0.6341 | 0.0559 |
| `m1-agent-06` | 125 | 0.0009 | 0.0055 | 0.0135 | 0.6886 | 0.0611 |
| `m1-agent-09` | 125 | 0.0020 | 0.0081 | 0.0153 | 0.6489 | 0.0574 |
| `m1-agent-10` | 125 | 0.0020 | 0.0087 | 0.0156 | 0.6886 | 0.0608 |
| `m2-agent-01` | 125 | 0.0024 | 0.0069 | 0.0141 | 0.6466 | 0.0573 |
| `m2-agent-02` | 125 | 0.0025 | 0.0061 | 0.0117 | 0.6399 | 0.0565 |
| `m2-agent-03` | 125 | 0.0025 | 0.0061 | 0.0116 | 0.6398 | 0.0565 |
| `m2-agent-04` | 125 | 0.0021 | 0.0060 | 0.0116 | 0.6258 | 0.0553 |
| `m2-agent-05` | 125 | 0.0025 | 0.0063 | 0.0119 | 0.6402 | 0.0565 |
| `m2-agent-06` | 125 | 0.0025 | 0.0059 | 0.0115 | 0.6632 | 0.0586 |
| `m2-agent-07` | 125 | 0.0022 | 0.0066 | 0.0117 | 0.6404 | 0.0565 |
| `m2-agent-08` | 125 | 0.0022 | 0.0062 | 0.0117 | 0.6369 | 0.0562 |
| `m2-agent-09` | 125 | 0.0025 | 0.0062 | 0.0117 | 0.6363 | 0.0561 |
| `m2-agent-10` | 125 | 0.0025 | 0.0061 | 0.0116 | 0.6342 | 0.0560 |
| `m3-agent-01` | 125 | 0.0025 | 0.0061 | 0.0116 | 0.6334 | 0.0559 |
| `m3-agent-02` | 125 | 0.0017 | 0.0051 | 0.0107 | 0.6646 | 0.0588 |
| `m3-agent-03` | 125 | 0.0026 | 0.0060 | 0.0115 | 0.6560 | 0.0579 |
| `m3-agent-04` | 125 | 0.0023 | 0.0060 | 0.0116 | 0.6609 | 0.0584 |
| `m3-agent-05` | 125 | 0.0026 | 0.0061 | 0.0119 | 0.6402 | 0.0565 |
| `m3-agent-06` | 125 | 0.0017 | 0.0051 | 0.0107 | 0.6467 | 0.0572 |
| `m3-agent-07` | 125 | 0.0026 | 0.0059 | 0.0115 | 0.6412 | 0.0566 |
| `m3-agent-08` | 125 | 0.0023 | 0.0059 | 0.0115 | 0.6654 | 0.0588 |
| `m3-agent-09` | 125 | 0.0010 | 0.0050 | 0.0106 | 0.6404 | 0.0566 |
| `m3-agent-10` | 125 | 0.0023 | 0.0057 | 0.0112 | 0.6580 | 0.0581 |

## Calibration cards (agent-reported coefficients)

Where the cohort converges on similar physics vs where it forks. Flattened from each agent's `coeffs.json`.

### `m1-agent-02`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.7,
    "s_scale": 0.94203,
    "delta_offset_rad": 0.00102,
    "K_us": 0.00304,
    "tau_yaw_s": 0.04592
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.984,
    "s_scale": 1.21716,
    "delta_offset_rad": -5e-05,
    "K_us": 0.00304,
    "tau_yaw_s": 0.05262
  },
  "TESLA_MODEL_3": {
    "L": 2.875,
    "s_scale": 1.0,
    "delta_offset_rad": 0.0,
    "K_us": 0.0025,
    "tau_yaw_s": 0.05
  },
  "_method": "Fit on 60% of segments per platform; model: yr_ss = v*(s_scale*delta - d0)/(L + K_us*v^2), then 1st-order lag with time constant tau_yaw_s.",
  "_tesla_note": "TESLA_MODEL_3 has no measured yaw-rate truth; coefficients are a reasonable EV-sedan prior (linear-tire understeer + 50 ms lag)."
}
```

### `m1-agent-03`
```json
{
  "_doc": "Per-platform yaw-rate correction coefficients fit on 70% train split, validated on 30% held-out. Model: yaw_rate = a * (v/L) * tan(delta) / (1 + K * v^2) + b. The bias term b corrects a systematic yaw-rate offset that, while small, dominates cross-track drift if neglected. For Tesla we have no measured-truth column, so we pass through V0 (a=1, K=0, b=0).",
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.7,
    "a": 0.9252444063595807,
    "K": 0.0008123125045696518,
    "b": -0.0042143449590920125
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.984,
    "a": 1.1449901885418456,
    "K": 0.000765135607718724,
    "b": 0.0007279523263131539
  },
  "TESLA_MODEL_3": {
    "L": 2.875,
    "a": 1.0,
    "K": 0.0,
    "b": 0.0
  }
}
```

### `m1-agent-04`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.7,
    "a": 0.9127536047016024,
    "b": 0.0007692876565060736,
    "delta_off": 0.0012208376981866274,
    "tau": 0.06378078127896805
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.984,
    "a": 1.1599450659882828,
    "b": 0.0008023134078587542,
    "delta_off": 1.3682104928342577e-05,
    "tau": 0.06877523527457137
  },
  "TESLA_MODEL_3": {
    "L": 2.875,
    "a": 1.0,
    "b": 0.0,
    "delta_off": 0.0,
    "tau": 0.0
  }
}
```

### `m1-agent-05`
```json
{
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.984,
    "Kus": 0.0025582137783147166,
    "delta_offset": -3.5224026005899095e-05,
    "gain": 1.1775403686346861
  },
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.7,
    "Kus": 0.003437862919442239,
    "delta_offset": 0.0012226023350801348,
    "gain": 0.9567393506201345
  },
  "TESLA_MODEL_3": {
    "L": 2.875,
    "Kus": 0.0,
    "delta_offset": 0.0,
    "gain": 1.0
  }
}
```

### `m2-agent-01`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.7,
    "K_us": 0.0045433459530302405,
    "delta0": 0.0013939755442043738,
    "tau": 0.059696812148648346
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.984,
    "K_us": 0.0008613349618482884,
    "delta0": -2.4463406949899732e-05,
    "tau": 0.058058773969275335
  },
  "TESLA_MODEL_3": {
    "L": 2.875,
    "K_us": 0.0007,
    "delta0": 0.0,
    "tau": 0.08
  }
}
```

### `m2-agent-02`
```json
{
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.984,
    "K_us": 0.0029345444115512595,
    "a_scale": 1.2040706547093705,
    "b_off": 3.374144913032861e-05,
    "tau": 0.06905323219403789,
    "train_rmse": 0.008957550273017442,
    "n_segments": 240
  },
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.7,
    "K_us": 0.003924190106391971,
    "a_scale": 0.9775595964191925,
    "b_off": -0.001242446303800499,
    "tau": 0.05905787473317712,
    "train_rmse": 0.005658956187764112,
    "n_segments": 175
  },
  "TESLA_MODEL_3": {
    "L": 2.875,
    "K_us": 0.0029345444115512595,
    "a_scale": 1.2040706547093705,
    "b_off": 3.374144913032861e-05,
    "tau": 0.06905323219403789,
    "train_rmse": null,
    "n_segments": 0,
    "note": "No yaw_rate_meas_rads in Tesla data; reusing Mach-E coefficients as a benign default."
  }
}
```

### `m2-agent-03`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "L_eff": 3.7874160302267805,
    "K": 0.0010601777605335054,
    "d0": 0.0012897224766212265,
    "tau": 0.05
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L_eff": 2.4765476192620257,
    "K": 0.0009714616153136761,
    "d0": 4.480994570776638e-05,
    "tau": 0.05
  }
}
```

### `m2-agent-04`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "delta_offset_rad": 0.00051637,
    "L_eff_m": 3.9825666188793982,
    "K_us": 0.002924411514488741,
    "tau_s": 0.05
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "delta_offset_rad": 0.000307999,
    "L_eff_m": 2.554146978403556,
    "K_us": 0.0018514873316044143,
    "tau_s": 0.08
  }
}
```

### `m2-agent-05`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.7,
    "g": 0.978386024867586,
    "K_us": 0.003952369466136279,
    "delta0": 0.0013386063106657791,
    "tau": 0.05245353568404573
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.984,
    "g": 1.212362348609587,
    "K_us": 0.0030155666104823165,
    "delta0": -0.00017873648699720767,
    "tau": 0.05847378305110825
  },
  "TESLA_MODEL_3": {
    "L": 2.875,
    "g": 1.0,
    "K_us": 0.003,
    "delta0": 0.0,
    "tau": 0.05
  }
}
```

### `m2-agent-06`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "K": 0.0009,
    "delta0": 0.0012,
    "scale": 0.93203,
    "L": 3.7,
    "tau": 0.06
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "K": 0.00088,
    "delta0": 0.0,
    "scale": 1.17364,
    "L": 2.984,
    "tau": 0.06
  },
  "TESLA_MODEL_3": {
    "K": 0.0008,
    "delta0": 0.0,
    "scale": 1.0,
    "L": 2.875,
    "tau": 0.06
  }
}
```

### `m2-agent-09`
```json
{
  "FORD_MUSTANG_MACH_E_MK1": {
    "s": 1.203330959234065,
    "K": 0.0029361363287092115,
    "bias": 0.00021448227575312877,
    "tau": 0.032147914442713796,
    "delay": 1
  },
  "FORD_F_150_LIGHTNING_MK1": {
    "s": 0.9772602779030508,
    "K": 0.003915796445879638,
    "bias": -0.004423910419199254,
    "tau": 0.022540457646443024,
    "delay": 1
  }
}
```

### `m2-agent-10`
```json
{
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.984,
    "K": 0.00275,
    "tau": 0.06,
    "s": 1.1930571109607484,
    "b0": 0.00021936029371554376
  },
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.7,
    "K": 0.00375,
    "tau": 0.06,
    "s": 0.9693239517582046,
    "b0": -0.004435874285029893
  }
}
```

### `m3-agent-01`
```json
{
  "_doc": "Per-platform fitted coefficients for the kinematic-bicycle steady-state yaw model: yr_ss = v * g * (delta - delta_0) / (L + K_us * v^2). Lightning uses two-stage fit (d0 from straight-driving rows, g and K_us from full data). Mach-E uses joint least-squares (lowest dev CTE). A first-order lag tau is applied on top.",
  "tau_s": 0.08,
  "FORD_F_150_LIGHTNING_MK1": {
    "g": 0.9567028992805204,
    "K_us": 0.0033801343956829,
    "delta_0": 0.0008461582112823263,
    "L": 3.7
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "g": 1.1725815243702862,
    "K_us": 0.0025152837759692456,
    "delta_0": 0.00013949413303459602,
    "L": 2.984
  }
}
```

### `m3-agent-02`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "g0": 0.9547252471876968,
    "g2": 0.30955433470955135,
    "delta0": -0.0012076703811611659,
    "K0": 0.004730621034575316,
    "K1": -4.650987485473428e-05,
    "tau": 0.06317565820147315,
    "L": 3.7
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "g0": 1.150573032079845,
    "g2": 0.8757198083908644,
    "delta0": 0.00027930003257062427,
    "K0": 0.0025878393724550054,
    "K1": -1.6405358020115646e-05,
    "tau": 0.07389236518027655,
    "L": 2.984
  }
}
```

### `m3-agent-03`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "g0": 0.9224096029662896,
    "g2": 0.15876361430939134,
    "delta0": -0.0010913875270846236,
    "L_eff": 3.6413019931403277,
    "K0": 0.004767766094094899,
    "K1": -5.858241730532427e-05,
    "tau": 0.0740452029657968
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "g0": 1.0219456519707983,
    "g2": 0.40092616819123517,
    "delta0": 5.9966690969289335e-05,
    "L_eff": 2.771534314392467,
    "K0": 0.0015320260055171069,
    "K1": 1.5004138297234027e-05,
    "tau": 0.08533887973933936
  }
}
```

### `m3-agent-04`
```json
{
  "version": "v2",
  "model": "ks_understeer_polysteer_lag",
  "platforms": {
    "FORD_F_150_LIGHTNING_MK1": {
      "g0": 0.9030042401515652,
      "g1": 0.24465438938383516,
      "delta0": 0.0011534229726781894,
      "K_us": 0.0028948051317225897,
      "tau": 0.062365871915759194,
      "L": 3.7,
      "n_segments_train": 131
    },
    "FORD_MUSTANG_MACH_E_MK1": {
      "g0": 1.1002549221289848,
      "g1": 0.5165245630067858,
      "delta0": -0.00010217216008262,
      "K_us": 0.0021117632272989097,
      "tau": 0.06796368743240064,
      "L": 2.984,
      "n_segments_train": 180
    }
  }
}
```

### `m3-agent-05`
```json
{
  "FORD_MUSTANG_MACH_E_MK1": {
    "g": 1.1935822683980741,
    "delta_offset": 0.00016378819390629683,
    "K_us": 0.0027507391842350546,
    "tau": 0.07010533877461887,
    "L": 2.984
  },
  "FORD_F_150_LIGHTNING_MK1": {
    "g": 0.9786307745986058,
    "delta_offset": -0.0012312582055424145,
    "K_us": 0.003976165863986497,
    "tau": 0.06037312785047078,
    "L": 3.7
  }
}
```

### `m3-agent-06`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.7,
    "g": 0.999852269902555,
    "delta0_platform": 0.0012652615927383102,
    "K_us": 0.004316983177712627,
    "tau": 0.06000021365433938,
    "self_delta0_blend": 0.0,
    "d0_fallback": 0.0012652615927383102
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.984,
    "g": 1.198731582043607,
    "delta0_platform": -4.2440277399239545e-05,
    "K_us": 0.0026746928298772552,
    "tau": 0.055620075247426924,
    "self_delta0_blend": 0.7,
    "d0_fallback": -0.0009502660161159785
  }
}
```

### `m3-agent-07`
```json
{
  "FORD_MUSTANG_MACH_E_MK1": {
    "g": 1.1762462360941122,
    "d0": 0.00010063505427400637,
    "K_us": 0.0026382633004772204,
    "tau": 0.06840716946070041,
    "g_v3": 1.1770261504574182,
    "d0_v3": 0.00014959445374349638,
    "K_us_v3": 0.0026591289393425076,
    "tau_v3": 0.06881984429222407,
    "alpha_v3": 3.414239845943319e-09,
    "g_v1": 1.173581598798327,
    "d0_v1": 9.779075692684366e-05,
    "K_us_v1": 0.0026023048615728033,
    "L": 2.984
  },
  "FORD_F_150_LIGHTNING_MK1": {
    "g": 0.9812529513258541,
    "d0": 0.0011869609888145339,
    "K_us": 0.0041443305277957445,
    "tau": 0.06130822211279313,
    "g_v3": 0.9812464336315232,
    "d0_v3": 0.0011870345278419555,
    "K_us_v3": 0.004144503544848034,
    "tau_v3": 0.06128822752272341,
    "alpha_v3": 3.986979263377587e-09,
    "g_v1": 0.9795065634523334,
    "d0_v1": 0.0011752337517999898,
    "K_us_v1": 0.004081817473342322,
    "L": 3.7
  }
}
```

### `m3-agent-08`
```json
{
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.984,
    "g0": 1.147725993732732,
    "g2": 0.9655593220523541,
    "delta0": -2.7081850677476107e-05,
    "K_us": 0.0023161900936763164,
    "tau": 0.07242177437719094
  },
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.7,
    "g0": 0.9355822723957319,
    "g2": 0.3723198294019272,
    "delta0": 0.0011705810669198063,
    "K_us": 0.0032679715315191748,
    "tau": 0.06330418589176087
  }
}
```

### `m3-agent-09`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "model": "v1_global_delta0",
    "g": 0.8633847850655261,
    "delta0": 0.001333845368641501,
    "L_eff": 3.262313536845297,
    "K_us": 0.00349772209138941,
    "tau": 0.05952805407230728
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "model": "v4_per_segment_delta0",
    "g": 0.8907859709885533,
    "L_eff": 2.2160488557450244,
    "K_us": 0.002016048675027096,
    "tau": 0.0690564359086768,
    "delta0_fallback": -0.00010084780741412298
  }
}
```

### `m3-agent-10`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "g0": 0.9676783007669604,
    "g2": 0.2968271411685613,
    "L_eff": 3.807326882698145,
    "K_us": 0.0034115094067706892,
    "delta0": 0.0013276275067902771,
    "tau": 0.06
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "g0": 1.0830317716737579,
    "g2": 0.7208104203442816,
    "L_eff": 2.7965042204881425,
    "K_us": 0.00236019497355297,
    "delta0": 0.00021014487211973025,
    "tau": 0.07
  }
}
```

## Reconstruction quality (substrate signal)

How many agents shipped the right artefacts to be canonically gradable. Failures here are a substrate / contract problem, not a model problem.

| format check | pass | fail |
|---|---|---|
| `agent_folder_exists` | 29 | 0 |
| `has_manifest_json` | 29 | 0 |
| `manifest_parsable` | 29 | 0 |
| `manifest_declares_predict_callable` | 29 | 0 |
| `manifest_declares_platform_support` | 29 | 0 |
| `has_predict_py` | 29 | 0 |
| `has_coeffs_json` | 22 | 7 |
| `has_report` | 25 | 4 |

**Failure reasons** (across the cohort):

- `import_failed` — 1 agent(s)

## Worst-of-cohort (among ok submissions)

**Lowest yaw Δ%**:
- `m1-agent-10` (+10.9%)
- `m1-agent-09` (+12.3%)
- `m2-agent-01` (+18.6%)

**Lowest CTE Δ%**:
- `m2-agent-01` (+15.1%)
- `m2-agent-05` (+18.4%)
- `m3-agent-05` (+19.2%)
