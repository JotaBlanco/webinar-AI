# Cohort canonical evaluation — 30 agents

- **idea**: `idea-01-lateral-attribution`
- **eval pool**: 534 held-out segments under `/Users/javiquix/Desktop/quixdev/F1/KB003/data/val-data`
- **V0 baselines**: yaw RMSE = **0.016274 rad/s** (1,353,874 samples); CTE RMSE = **254.2605 m** (502,632 bins)
- **reconstructed**: 30 ok / 0 failed (wall 14.26s, concurrency 8)

## Headline

- 🥇 **Best yaw**: `m3-agent-04` (+56.8%)
- 🥇 **Best CTE**: `m3-agent-04` (+72.3%)
- 🎯 **Winning both KPIs ≥ +30%** (30 agents): `m3-agent-04`, `m3-agent-09`, `m3-agent-02`, `m3-agent-03`, `m3-agent-05`, `m3-agent-06`, `m3-agent-07`, `m3-agent-08`, `m3-agent-10`, `m3-agent-01`, `m2-agent-10`, `m1-agent-01`, `m2-agent-09`, `m2-agent-06`, `m2-agent-07`, `m1-agent-09`, `m2-agent-02`, `m1-agent-07`, `m2-agent-04`, `m2-agent-03`, `m2-agent-05`, `m1-agent-02`, `m1-agent-05`, `m1-agent-03`, `m2-agent-01`, `m1-agent-04`, `m1-agent-10`, `m1-agent-06`, `m2-agent-08`, `m1-agent-08`

## Performance by family

Each family is a comparison group (e.g. `module-N`). Improvement %s computed against the SAME V0 baseline on the SAME held-out pool.

| family | n ok / total | yaw Δ% (mean ± σ) | CTE Δ% (mean ± σ) | failures |
|---|---|---|---|---|
| `module-1` | 10/10 | +48.0% ± 2.8% (med +48.6%) | +54.9% ± 2.3% (med +55.8%) | 0 |
| `module-2` | 10/10 | +49.5% ± 1.4% (med +49.6%) | +57.3% ± 1.4% (med +56.9%) | 0 |
| `module-3` | 10/10 | +56.5% ± 0.6% (med +56.6%) | +72.2% ± 0.3% (med +72.2%) | 0 |

## Token expenditure

Sourced from each agent's Claude Code subagent transcript (`~/.claude/projects/<proj>/*/subagents/agent-*.jsonl`). Tokens summed across every assistant turn of the latest-mtime run per agent. Cohort total: **90.46M tokens** across 30 agents (median 2.67M/agent, median 63 assistant turns).

| family | n | total tokens | median / agent | median turns | input | output | cache_create | cache_read |
|---|---|---|---|---|---|---|---|---|
| `module-1` | 10 | **23.38M** | 2.38M | 62 | 734 | 176.5k | 824.6k | 22.38M |
| `module-2` | 10 | **25.69M** | 2.24M | 54 | 705 | 130.0k | 1.14M | 24.42M |
| `module-3` | 10 | **41.38M** | 3.50M | 67 | 886 | 146.2k | 1.82M | 39.41M |

**Per-agent token expenditure (sorted by total):**

| agent | family | turns | total | input | output | cache_create | cache_read | yaw Δ% | CTE Δ% |
|---|---|---|---|---|---|---|---|---|---|
| `m3-agent-06` | `module-3` | 107 | **8.18M** | 132 | 23.6k | 432.5k | 7.72M | +56.6% | +72.2% |
| `m3-agent-01` | `module-3` | 94 | **6.78M** | 109 | 28.6k | 281.9k | 6.47M | +54.5% | +71.4% |
| `m3-agent-05` | `module-3` | 106 | **6.03M** | 146 | 14.9k | 326.9k | 5.68M | +56.6% | +72.2% |
| `m2-agent-05` | `module-2` | 83 | **4.45M** | 93 | 18.2k | 147.6k | 4.29M | +48.7% | +59.1% |
| `m3-agent-03` | `module-3` | 72 | **3.96M** | 82 | 16.2k | 125.9k | 3.81M | +56.7% | +72.2% |
| `m3-agent-08` | `module-3` | 68 | **3.84M** | 83 | 13.8k | 134.6k | 3.70M | +56.6% | +72.2% |
| `m2-agent-08` | `module-2` | 76 | **3.73M** | 96 | 13.2k | 230.0k | 3.49M | +46.1% | +57.0% |
| `m2-agent-07` | `module-2` | 69 | **3.61M** | 79 | 14.2k | 98.4k | 3.50M | +50.7% | +56.9% |
| `m1-agent-09` | `module-1` | 79 | **3.54M** | 106 | 19.8k | 143.4k | 3.37M | +50.2% | +55.4% |
| `m3-agent-07` | `module-3` | 66 | **3.16M** | 76 | 12.7k | 104.0k | 3.04M | +56.6% | +72.2% |
| `m3-agent-09` | `module-3` | 61 | **3.02M** | 71 | 7.6k | 103.9k | 2.91M | +56.8% | +72.2% |
| `m1-agent-08` | `module-1` | 74 | **2.96M** | 82 | 18.4k | 80.3k | 2.86M | +40.4% | +56.6% |
| `m3-agent-10` | `module-3` | 65 | **2.86M** | 75 | 12.9k | 91.2k | 2.75M | +56.6% | +72.2% |
| `m3-agent-02` | `module-3` | 61 | **2.83M** | 71 | 13.1k | 95.6k | 2.72M | +56.8% | +72.2% |
| `m2-agent-02` | `module-2` | 68 | **2.68M** | 78 | 16.0k | 92.4k | 2.58M | +49.8% | +59.4% |
| `m1-agent-02` | `module-1` | 66 | **2.66M** | 78 | 21.0k | 82.8k | 2.56M | +48.6% | +57.2% |
| `m1-agent-10` | `module-1` | 64 | **2.45M** | 76 | 18.6k | 80.4k | 2.35M | +47.8% | +49.5% |
| `m1-agent-07` | `module-1` | 62 | **2.41M** | 70 | 22.7k | 71.0k | 2.32M | +49.6% | +53.4% |
| `m2-agent-03` | `module-2` | 52 | **2.35M** | 67 | 10.3k | 117.0k | 2.22M | +49.2% | +57.2% |
| `m1-agent-04` | `module-1` | 63 | **2.34M** | 71 | 17.6k | 73.2k | 2.25M | +48.0% | +56.1% |
| `m1-agent-05` | `module-1` | 62 | **2.25M** | 74 | 16.7k | 76.8k | 2.16M | +48.6% | +55.2% |
| `m2-agent-09` | `module-2` | 55 | **2.14M** | 65 | 14.3k | 80.5k | 2.05M | +50.9% | +56.4% |
| `m2-agent-10` | `module-2` | 53 | **2.11M** | 68 | 11.5k | 115.5k | 1.98M | +51.0% | +54.7% |
| `m1-agent-01` | `module-1` | 53 | **1.88M** | 65 | 17.3k | 94.7k | 1.77M | +51.0% | +56.6% |
| `m2-agent-04` | `module-2` | 45 | **1.83M** | 55 | 9.7k | 112.0k | 1.71M | +49.5% | +59.1% |
| `m1-agent-06` | `module-1` | 54 | **1.73M** | 66 | 15.2k | 74.6k | 1.64M | +46.9% | +52.3% |
| `m2-agent-06` | `module-2` | 43 | **1.66M** | 53 | 13.7k | 79.9k | 1.57M | +50.9% | +56.4% |
| `m1-agent-03` | `module-1` | 38 | **1.17M** | 46 | 9.2k | 47.3k | 1.11M | +48.5% | +56.7% |
| `m2-agent-01` | `module-2` | 41 | **1.13M** | 51 | 8.9k | 67.3k | 1.05M | +48.4% | +56.9% |
| `m3-agent-04` | `module-3` | 26 | **740.2k** | 41 | 2.9k | 125.0k | 612.3k | +56.8% | +72.3% |

## Per-platform breakdown

How each platform fared when supported. Mean across all agents that declared support AND ran successfully on that platform.

| platform | agents | yaw Δ% (mean ± σ) | CTE Δ% (mean ± σ) |
|---|---|---|---|
| `FORD_F_150_LIGHTNING_MK1` | 30 | +21.7% ± 2.3% (med +22.4%) | +72.8% ± 1.1% (med +72.5%) |
| `FORD_MUSTANG_MACH_E_MK1` | 30 | +55.7% ± 7.8% (med +54.8%) | +56.1% ± 10.7% (med +50.7%) |
| `HYUNDAI_IONIQ_5` | 30 | +55.4% ± 4.3% (med +54.2%) | +61.8% ± 8.0% (med +59.0%) |

## Per-agent canonical scorecard

| agent | family | status | yaw V0 | yaw final | yaw Δ% | CTE V0 | CTE final | CTE Δ% | n seg ok/total | wall |
|---|---|---|---|---|---|---|---|---|---|---|
| `m1-agent-01` | `module-1` | ok | 0.016274 | 0.007971 | **+51.0%** | 254.26 | 110.23 | **+56.6%** | 534/534 | 3.42s |
| `m1-agent-02` | `module-1` | ok | 0.016274 | 0.008358 | **+48.6%** | 254.26 | 108.76 | **+57.2%** | 534/534 | 3.42s |
| `m1-agent-03` | `module-1` | ok | 0.016274 | 0.008381 | **+48.5%** | 254.26 | 110.20 | **+56.7%** | 534/534 | 4.52s |
| `m1-agent-04` | `module-1` | ok | 0.016274 | 0.008461 | **+48.0%** | 254.26 | 111.68 | **+56.1%** | 534/534 | 3.42s |
| `m1-agent-05` | `module-1` | ok | 0.016274 | 0.008360 | **+48.6%** | 254.26 | 113.83 | **+55.2%** | 534/534 | 4.95s |
| `m1-agent-06` | `module-1` | ok | 0.016274 | 0.008638 | **+46.9%** | 254.26 | 121.35 | **+52.3%** | 534/534 | 3.42s |
| `m1-agent-07` | `module-1` | ok | 0.016274 | 0.008199 | **+49.6%** | 254.26 | 118.37 | **+53.4%** | 534/534 | 6.17s |
| `m1-agent-08` | `module-1` | ok | 0.016274 | 0.009695 | **+40.4%** | 254.26 | 110.30 | **+56.6%** | 534/534 | 5.67s |
| `m1-agent-09` | `module-1` | ok | 0.016274 | 0.008111 | **+50.2%** | 254.26 | 113.32 | **+55.4%** | 534/534 | 2.7s |
| `m1-agent-10` | `module-1` | ok | 0.016274 | 0.008496 | **+47.8%** | 254.26 | 128.49 | **+49.5%** | 534/534 | 7.76s |
| `m2-agent-01` | `module-2` | ok | 0.016274 | 0.008391 | **+48.4%** | 254.26 | 109.59 | **+56.9%** | 534/534 | 2.3s |
| `m2-agent-02` | `module-2` | ok | 0.016274 | 0.008167 | **+49.8%** | 254.26 | 103.33 | **+59.4%** | 534/534 | 2.27s |
| `m2-agent-03` | `module-2` | ok | 0.016274 | 0.008264 | **+49.2%** | 254.26 | 108.92 | **+57.2%** | 534/534 | 2.35s |
| `m2-agent-04` | `module-2` | ok | 0.016274 | 0.008224 | **+49.5%** | 254.26 | 104.04 | **+59.1%** | 534/534 | 2.42s |
| `m2-agent-05` | `module-2` | ok | 0.016274 | 0.008350 | **+48.7%** | 254.26 | 104.04 | **+59.1%** | 534/534 | 2.45s |
| `m2-agent-06` | `module-2` | ok | 0.016274 | 0.007997 | **+50.9%** | 254.26 | 110.97 | **+56.4%** | 534/534 | 2.37s |
| `m2-agent-07` | `module-2` | ok | 0.016274 | 0.008023 | **+50.7%** | 254.26 | 109.64 | **+56.9%** | 534/534 | 2.46s |
| `m2-agent-08` | `module-2` | ok | 0.016274 | 0.008772 | **+46.1%** | 254.26 | 109.37 | **+57.0%** | 534/534 | 2.39s |
| `m2-agent-09` | `module-2` | ok | 0.016274 | 0.007997 | **+50.9%** | 254.26 | 110.97 | **+56.4%** | 534/534 | 2.49s |
| `m2-agent-10` | `module-2` | ok | 0.016274 | 0.007970 | **+51.0%** | 254.26 | 115.23 | **+54.7%** | 534/534 | 2.46s |
| `m3-agent-01` | `module-3` | ok | 0.016274 | 0.007399 | **+54.5%** | 254.26 | 72.79 | **+71.4%** | 534/534 | 2.85s |
| `m3-agent-02` | `module-3` | ok | 0.016274 | 0.007038 | **+56.8%** | 254.26 | 70.65 | **+72.2%** | 534/534 | 2.87s |
| `m3-agent-03` | `module-3` | ok | 0.016274 | 0.007045 | **+56.7%** | 254.26 | 70.59 | **+72.2%** | 534/534 | 2.9s |
| `m3-agent-04` | `module-3` | ok | 0.016274 | 0.007026 | **+56.8%** | 254.26 | 70.40 | **+72.3%** | 534/534 | 2.89s |
| `m3-agent-05` | `module-3` | ok | 0.016274 | 0.007065 | **+56.6%** | 254.26 | 70.58 | **+72.2%** | 534/534 | 2.87s |
| `m3-agent-06` | `module-3` | ok | 0.016274 | 0.007065 | **+56.6%** | 254.26 | 70.58 | **+72.2%** | 534/534 | 2.89s |
| `m3-agent-07` | `module-3` | ok | 0.016274 | 0.007065 | **+56.6%** | 254.26 | 70.58 | **+72.2%** | 534/534 | 2.87s |
| `m3-agent-08` | `module-3` | ok | 0.016274 | 0.007065 | **+56.6%** | 254.26 | 70.58 | **+72.2%** | 534/534 | 2.75s |
| `m3-agent-09` | `module-3` | ok | 0.016274 | 0.007032 | **+56.8%** | 254.26 | 70.58 | **+72.2%** | 534/534 | 2.67s |
| `m3-agent-10` | `module-3` | ok | 0.016274 | 0.007065 | **+56.6%** | 254.26 | 70.58 | **+72.2%** | 534/534 | 2.69s |

## Per-segment yaw-RMSE distribution (spread within each agent)

Pooled RMSE can hide that an agent is great on most segments but pathological on a few. These columns expose that.

| agent | n segs | min | median | mean | max | std |
|---|---|---|---|---|---|---|
| `m1-agent-01` | 522 | 0.0017 | 0.0061 | 0.0079 | 0.6342 | 0.0277 |
| `m1-agent-02` | 522 | 0.0015 | 0.0068 | 0.0084 | 0.6384 | 0.0279 |
| `m1-agent-03` | 522 | 0.0016 | 0.0069 | 0.0084 | 0.6394 | 0.0279 |
| `m1-agent-04` | 522 | 0.0015 | 0.0070 | 0.0085 | 0.6552 | 0.0285 |
| `m1-agent-05` | 522 | 0.0017 | 0.0068 | 0.0084 | 0.6536 | 0.0284 |
| `m1-agent-06` | 522 | 0.0016 | 0.0071 | 0.0087 | 0.6336 | 0.0277 |
| `m1-agent-07` | 522 | 0.0016 | 0.0064 | 0.0082 | 0.6383 | 0.0279 |
| `m1-agent-08` | 522 | 0.0017 | 0.0081 | 0.0098 | 0.6339 | 0.0278 |
| `m1-agent-09` | 522 | 0.0016 | 0.0063 | 0.0081 | 0.6314 | 0.0276 |
| `m1-agent-10` | 522 | 0.0017 | 0.0063 | 0.0084 | 0.6368 | 0.0278 |
| `m2-agent-01` | 522 | 0.0016 | 0.0066 | 0.0084 | 0.6248 | 0.0273 |
| `m2-agent-02` | 522 | 0.0016 | 0.0064 | 0.0081 | 0.6237 | 0.0272 |
| `m2-agent-03` | 522 | 0.0018 | 0.0066 | 0.0083 | 0.6437 | 0.0280 |
| `m2-agent-04` | 522 | 0.0016 | 0.0064 | 0.0081 | 0.6223 | 0.0271 |
| `m2-agent-05` | 522 | 0.0016 | 0.0063 | 0.0083 | 0.6510 | 0.0284 |
| `m2-agent-06` | 522 | 0.0016 | 0.0062 | 0.0080 | 0.6341 | 0.0277 |
| `m2-agent-07` | 522 | 0.0017 | 0.0062 | 0.0080 | 0.6375 | 0.0278 |
| `m2-agent-08` | 522 | 0.0016 | 0.0068 | 0.0087 | 0.6435 | 0.0282 |
| `m2-agent-09` | 522 | 0.0016 | 0.0062 | 0.0080 | 0.6341 | 0.0277 |
| `m2-agent-10` | 522 | 0.0015 | 0.0060 | 0.0078 | 0.6581 | 0.0286 |
| `m3-agent-01` | 522 | 0.0010 | 0.0050 | 0.0073 | 0.6308 | 0.0278 |
| `m3-agent-02` | 522 | 0.0010 | 0.0049 | 0.0069 | 0.6394 | 0.0280 |
| `m3-agent-03` | 522 | 0.0010 | 0.0049 | 0.0069 | 0.6399 | 0.0280 |
| `m3-agent-04` | 522 | 0.0010 | 0.0049 | 0.0069 | 0.6399 | 0.0280 |
| `m3-agent-05` | 522 | 0.0010 | 0.0049 | 0.0069 | 0.6404 | 0.0280 |
| `m3-agent-06` | 522 | 0.0010 | 0.0049 | 0.0069 | 0.6404 | 0.0280 |
| `m3-agent-07` | 522 | 0.0010 | 0.0049 | 0.0069 | 0.6404 | 0.0280 |
| `m3-agent-08` | 522 | 0.0010 | 0.0049 | 0.0069 | 0.6404 | 0.0280 |
| `m3-agent-09` | 522 | 0.0010 | 0.0049 | 0.0069 | 0.6399 | 0.0280 |
| `m3-agent-10` | 522 | 0.0010 | 0.0049 | 0.0069 | 0.6404 | 0.0280 |

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
  "coeffs": {
    "FORD_F_150_LIGHTNING_MK1": {
      "L_eff": 3.714674413041366,
      "K_us": 0.003030409078344079,
      "gain": 0.9457494934611176,
      "bias": -0.0055849733484417486,
      "tau": -0.06336610199052815
    },
    "FORD_MUSTANG_MACH_E_MK1": {
      "L_eff": 2.9282638905275795,
      "K_us": 0.0029524956693629404,
      "gain": 1.1587807802011336,
      "bias": 0.00187100684231396,
      "tau": -0.054222241978696524
    },
    "HYUNDAI_IONIQ_5": {
      "L_eff": 3.019851587366396,
      "K_us": 0.0037457278776179947,
      "gain": 0.9561673653833413,
      "bias": 0.002648583437005523,
      "tau": -0.029235120983884498
    }
  }
}
```

### `m2-agent-02`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "L_eff": 3.941941906538264,
    "K_us": 0.0037788233688761494,
    "b": -0.005450661568006636,
    "tau": -0.08207658150714123
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L_eff": 2.5622977171066155,
    "K_us": 0.002745633390344498,
    "b": 0.00039676132180812505,
    "tau": -0.02283428861943423
  },
  "HYUNDAI_IONIQ_5": {
    "L_eff": 3.0387877407606987,
    "K_us": 0.004732031059157526,
    "b": 0.0019402727789656954,
    "tau": -0.038122141286844304
  },
  "TESLA_MODEL_3": null
}
```

### `m2-agent-03`
```json
{
  "_notes": "V4 model: yr = v * (delta - delta_off - c3 * delta^3) / (L + K_us * v^2) + tau * d(delta)/dt + bias. Fitted per-platform with L-BFGS-B on yaw RMSE objective (route-grouped 80/20 train-dev split). Tesla deliberately set to all-zeros for V0 passthrough since the platform's truth column IS the V0 KS output (no independent measurement).",
  "L": {
    "TESLA_MODEL_3": 2.875,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.7,
    "HYUNDAI_IONIQ_5": 3.0
  },
  "coeffs": {
    "TESLA_MODEL_3": {
      "K_us": 0.0,
      "bias": 0.0,
      "tau": 0.0,
      "delta_off": 0.0,
      "c3": 0.0
    },
    "FORD_MUSTANG_MACH_E_MK1": {
      "K_us": 0.000961086877702429,
      "bias": 0.0008803388664213581,
      "tau": -0.16574900177925186,
      "delta_off": 9.852443047820677e-05,
      "c3": -1.8560781074219364
    },
    "FORD_F_150_LIGHTNING_MK1": {
      "K_us": 0.004611444613160498,
      "bias": -0.004404850174101399,
      "tau": -0.08625767593007348,
      "delta_off": 5.739849266899158e-05,
      "c3": 0.0004645633450317248
    },
    "HYUNDAI_IONIQ_5": {
      "K_us": 0.004178627615524952,
      "bias": 0.0009723808331481673,
      "tau": -0.090
```

### `m2-agent-04`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "L_eff": 3.96394551474604,
    "Kus": 0.003414866921617812,
    "bias": -0.005292773687032753,
    "tau": -0.06157679065853846
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L_eff": 2.569483805164948,
    "Kus": 0.0025788290081397765,
    "bias": 0.0011230859100703557,
    "tau": -0.04709908110775255
  },
  "HYUNDAI_IONIQ_5": {
    "L_eff": 3.008377713685593,
    "Kus": 0.005133658670161866,
    "bias": 0.0019487320168033527,
    "tau": -0.04867295794401198
  },
  "TESLA_MODEL_3": {
    "dummy": 0.0
  }
}
```

### `m2-agent-05`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "L_eff": 4.070447954653418,
    "K_us": 0.0033690686027498975,
    "tau": -0.05207958376677542,
    "bias": -0.005033607143362777
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L_eff": 2.634208485873725,
    "K_us": 0.0020512679669922374,
    "tau": -0.03834254742316755,
    "bias": 0.0009574176186544922
  },
  "HYUNDAI_IONIQ_5": {
    "L_eff": 3.050939316421378,
    "K_us": 0.005006467603752251,
    "tau": -0.06330771299219948,
    "bias": 0.002544213895491465
  },
  "TESLA_MODEL_3": {
    "L_eff": 2.875,
    "K_us": 0.0,
    "tau": 0.0,
    "bias": 0.0
  }
}
```

### `m2-agent-06`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "platform": "FORD_F_150_LIGHTNING_MK1",
    "L": 3.818759956786134,
    "Kus": 0.0039432563422251285,
    "tau": -0.05861405092290705,
    "bias": -0.004437268567086911,
    "rmse_fit": 0.0054979371675811595,
    "n": 430990,
    "converged": true
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "platform": "FORD_MUSTANG_MACH_E_MK1",
    "L": 2.4997194805464074,
    "Kus": 0.0024024802542751437,
    "tau": -0.06630813663570458,
    "bias": 0.00022227158439854945,
    "rmse_fit": 0.00894166094428278,
    "n": 615175,
    "converged": true
  },
  "HYUNDAI_IONIQ_5": {
    "platform": "HYUNDAI_IONIQ_5",
    "L": 3.100074393615448,
    "Kus": 0.0035463766130646316,
    "tau": -0.05358525493540066,
    "bias": 0.001966636983251082,
    "rmse_fit": 0.008266374104865987,
    "n": 2042270,
    "converged": true
  }
}
```

### `m2-agent-07`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "gain": 0.26155354286406696,
    "K_us": 0.0010348161168794911,
    "tau": -0.059233445160195526,
    "delta_off": 0.0012750824213680152,
    "L_nominal": 3.7,
    "rmse_train": 0.005575700740201668,
    "n_train": 200000,
    "converged": true
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "gain": 0.4035178594047913,
    "K_us": 0.0009821532560097713,
    "tau": -0.008033810413798562,
    "delta_off": -2.5853693055615083e-05,
    "L_nominal": 2.984,
    "rmse_train": 0.009471760429205004,
    "n_train": 200000,
    "converged": true
  },
  "HYUNDAI_IONIQ_5": {
    "gain": 0.32227701098043227,
    "K_us": 0.0011334962349270976,
    "tau": -0.05314414110647487,
    "delta_off": -0.0005261292135057335,
    "L_nominal": 3.0,
    "rmse_train": 0.008154152273394789,
    "n_train": 200000,
    "converged": true
  },
  "TESLA_MODEL_3": {
    "gain": 0.34782608695652173,
    "K_us": 0.0,
    "tau": 0.0,
    "delta_off": 0.0,
    "L_nominal": 2.875,
    "passthrough": true
  }
}
```

### `m2-agent-08`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.7,
    "K_us": 0.004622784347956018,
    "tau": -0.05460138412592134,
    "bias": -0.004482561615678892,
    "train_mse": 3.3520085701320475e-05,
    "train_rmse": 0.005789653331704799,
    "n_samples": 430990,
    "n_segments": 164,
    "converged": true,
    "message": "CONVERGENCE: NORM OF PROJECTED GRADIENT <= PGTOL"
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.984,
    "K_us": 0.0008351228965168481,
    "tau": -0.09459794094766563,
    "bias": 0.00054055263346224,
    "train_mse": 0.00017605613840148047,
    "train_rmse": 0.01326861478834473,
    "n_samples": 615175,
    "n_segments": 232,
    "converged": true,
    "message": "CONVERGENCE: NORM OF PROJECTED GRADIENT <= PGTOL"
  },
  "HYUNDAI_IONIQ_5": {
    "L": 2.95,
    "K_us": 0.004646731366208564,
    "tau": -0.04946605447751251,
    "bias": 0.0018472769568295111,
    "train_mse": 7.578893405982132e-05,
    "train_rmse": 0.008705684008727937,
    "n_samples": 2042270,
    "n_segments": 785,
    "converged": true,
    "message": "CONVERGENCE: NORM OF PROJECTED GRADIENT <= PGTOL"
  }
}
```

### `m2-agent-09`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "L": 3.8178518693887766,
    "Kus": 0.00395147084169022,
    "tau": -0.058687025047791365,
    "bias": -0.00444146460779491
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "L": 2.4997120055712387,
    "Kus": 0.002403424695943812,
    "tau": -0.06620984390299643,
    "bias": 0.00022345054281425354
  },
  "HYUNDAI_IONIQ_5": {
    "L": 3.099810382947127,
    "Kus": 0.0035472352224324858,
    "tau": -0.05358495723063911,
    "bias": 0.001965363779679206
  }
}
```

### `m2-agent-10`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "s_d": 0.9300245172021879,
    "c_d": 0.347294150023435,
    "tau_d": -0.05773764830098028,
    "K_us": 0.003240471803333766,
    "b": -0.004299834214218103,
    "L": 3.7
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "s_d": 1.1508056993666387,
    "c_d": 0.7498585082419895,
    "tau_d": -0.07607250144234215,
    "K_us": 0.0022785419555576775,
    "b": 0.0003167396785048121,
    "L": 2.984
  },
  "HYUNDAI_IONIQ_5": {
    "s_d": 0.9422644146648296,
    "c_d": 0.3465308670029774,
    "tau_d": -0.050503079814885346,
    "K_us": 0.002862544790766583,
    "b": 0.0022556662651586025,
    "L": 3.0
  },
  "TESLA_MODEL_3": {
    "passthrough": true
  }
}
```

### `m3-agent-01`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "use_per_segment_delta0": false,
    "delta0_fallback": 0.0,
    "g": 0.837566273970069,
    "L_eff": 3.268209123755641,
    "K_us": 0.0030867190166670422,
    "tau": 0.06250429810813812,
    "delta0": 0.0013772165596965772
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "use_per_segment_delta0": true,
    "delta0_fallback": 0.0,
    "g": 0.8689392647920121,
    "L_eff": 2.227860743811346,
    "K_us": 0.0015375118933521228,
    "tau": 0.048005187766273924
  },
  "HYUNDAI_IONIQ_5": {
    "use_per_segment_delta0": true,
    "delta0_fallback": 0.0,
    "g": 0.9036447880498372,
    "L_eff": 2.9067538688854606,
    "K_us": 0.002172067149911832,
    "tau": 0.021561438947319593
  },
  "TESLA_MODEL_3": {
    "passthrough": true
  }
}
```

### `m3-agent-02`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "g": 0.8599716540800916,
    "L_eff": 3.260802128118046,
    "K_us": 0.0033605485538025595,
    "tau": 0.058798336746219135,
    "delta0": 0.0012445223286377857,
    "use_per_segment_delta0": false
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "g": 0.8948751688442338,
    "L_eff": 2.218474888909999,
    "K_us": 0.002002066992546276,
    "tau": 0.06321825538415474,
    "delta0": -0.0001,
    "use_per_segment_delta0": true
  },
  "HYUNDAI_IONIQ_5": {
    "g": 0.928157495232038,
    "L_eff": 2.890194195032293,
    "K_us": 0.002716802199963435,
    "tau": 0.051288867659338114,
    "delta0": 0.0005262026839657872,
    "use_per_segment_delta0": true
  }
}
```

### `m3-agent-03`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "use_per_segment_delta0": false,
    "delta0": 0.00127,
    "g": 0.9789,
    "L_eff": 3.705,
    "K_us": 0.00393,
    "tau": 0.0591
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "use_per_segment_delta0": true,
    "delta0_fallback": -0.0001,
    "g": 0.891,
    "L_eff": 2.22,
    "K_us": 0.0015,
    "tau": 0.069
  },
  "HYUNDAI_IONIQ_5": {
    "use_per_segment_delta0": true,
    "delta0_fallback": 0.00014,
    "g": 0.9655,
    "L_eff": 3.0,
    "K_us": 0.00287,
    "tau": 0.051
  }
}
```

### `m3-agent-04`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "g": 0.8627559173927216,
    "L_eff": 3.2661642837279934,
    "K_us": 0.003399629365556295,
    "tau": 0.05764217451751205,
    "delta0": 0.0011797692301086372,
    "delta0_fallback": 0.0011797692301086372,
    "use_per_segment_delta0": false,
    "train_rmse": 0.005285188367801501,
    "dev_rmse": 0.006580546885659461,
    "bias_spread_std": null
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "g": 1.2845766366025777,
    "L_eff": 3.185078856835661,
    "K_us": 0.002783912493950955,
    "tau": 0.06245560987504152,
    "delta0": -0.0019790637549735985,
    "delta0_fallback": -0.0019790637549735985,
    "use_per_segment_delta0": true,
    "train_rmse": 0.008444302053948288,
    "dev_rmse": 0.008286227301504138,
    "bias_spread_std": null
  },
  "HYUNDAI_IONIQ_5": {
    "g": 0.9454031576502736,
    "L_eff": 2.9345636591691626,
    "K_us": 0.0028198034203513055,
    "tau": 0.0507163687871907,
    "delta0": 0.0004041780050478772,
    "delta0_fallback": 0.0004041780050478772,
    "use_per_segment_delta0": true,
    "train_rmse": 0.007930751971921808,
    "dev_rmse": 0.00660747263955304,
    "bias_spread_std": null
  }
}
```

### `m3-agent-05`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "use_per_segment_delta0": false,
    "delta0": 0.00133,
    "g": 0.863,
    "L_eff": 3.26,
    "K_us": 0.0035,
    "tau": 0.06
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "use_per_segment_delta0": true,
    "delta0_fallback": -0.0001,
    "g": 0.891,
    "L_eff": 2.22,
    "K_us": 0.0015,
    "tau": 0.069
  },
  "HYUNDAI_IONIQ_5": {
    "use_per_segment_delta0": true,
    "delta0_fallback": 0.0,
    "g": 0.938,
    "L_eff": 2.887,
    "K_us": 0.00289,
    "tau": 0.062
  }
}
```

### `m3-agent-06`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "use_per_segment_delta0": false,
    "delta0": 0.00133,
    "g": 0.863,
    "L_eff": 3.26,
    "K_us": 0.0035,
    "tau": 0.06
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "use_per_segment_delta0": true,
    "delta0_fallback": -0.0001,
    "g": 0.891,
    "L_eff": 2.22,
    "K_us": 0.0015,
    "tau": 0.069
  },
  "HYUNDAI_IONIQ_5": {
    "use_per_segment_delta0": true,
    "delta0_fallback": 0.0,
    "g": 0.938,
    "L_eff": 2.887,
    "K_us": 0.00289,
    "tau": 0.062
  }
}
```

### `m3-agent-07`
```json
{
  "params": {
    "FORD_F_150_LIGHTNING_MK1": {
      "g": 0.863,
      "L_eff": 3.26,
      "K_us": 0.0035,
      "tau": 0.06,
      "delta0": 0.00133
    },
    "FORD_MUSTANG_MACH_E_MK1": {
      "g": 0.891,
      "L_eff": 2.22,
      "K_us": 0.0015,
      "tau": 0.069,
      "delta0": -0.0001
    },
    "HYUNDAI_IONIQ_5": {
      "g": 0.938,
      "L_eff": 2.887,
      "K_us": 0.00289,
      "tau": 0.062,
      "delta0": 0.0
    }
  },
  "gates": {
    "FORD_F_150_LIGHTNING_MK1": false,
    "FORD_MUSTANG_MACH_E_MK1": true,
    "HYUNDAI_IONIQ_5": true,
    "TESLA_MODEL_3": false
  },
  "_note": "Coeffs from references/anti-patterns.md \u00a7 'The legal cousin'. Scipy refit yielded ~equal headline KPIs (yaw 0.006193 vs 0.005874, cte 55.97 vs 56.81), with wide train/dev gap on Lightning \u2014 sticking with recipe values."
}
```

### `m3-agent-08`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "use_per_segment_delta0": false,
    "delta0": 0.00133,
    "g": 0.863,
    "L_eff": 3.26,
    "K_us": 0.0035,
    "tau": 0.06
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "use_per_segment_delta0": true,
    "delta0_fallback": -0.0001,
    "g": 0.891,
    "L_eff": 2.22,
    "K_us": 0.0015,
    "tau": 0.069
  },
  "HYUNDAI_IONIQ_5": {
    "use_per_segment_delta0": true,
    "delta0_fallback": 0.0,
    "g": 0.938,
    "L_eff": 2.887,
    "K_us": 0.00289,
    "tau": 0.062
  }
}
```

### `m3-agent-09`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "use_per_segment_delta0": false,
    "g": 0.861467724254003,
    "L_eff": 3.260599776852266,
    "K_us": 0.00345816411072901,
    "tau": 0.05905887882576319,
    "delta0": 0.0012709660234224572
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "use_per_segment_delta0": true,
    "g": 1.1962944318242874,
    "L_eff": 2.9774243793659734,
    "K_us": 0.0026382390064948746,
    "tau": 0.06864314850865824,
    "delta0_fallback": -0.005108527372341619
  },
  "HYUNDAI_IONIQ_5": {
    "use_per_segment_delta0": true,
    "g": 0.9295844367980997,
    "L_eff": 2.888504022529887,
    "K_us": 0.0027606344445320796,
    "tau": 0.05101967952867051,
    "delta0_fallback": 0.0001354678283966721
  }
}
```

### `m3-agent-10`
```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "use_per_segment_delta0": false,
    "delta0": 0.00133,
    "g": 0.863,
    "L_eff": 3.26,
    "K_us": 0.0035,
    "tau": 0.06
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "use_per_segment_delta0": true,
    "delta0_fallback": -0.0001,
    "g": 0.891,
    "L_eff": 2.22,
    "K_us": 0.0015,
    "tau": 0.069
  },
  "HYUNDAI_IONIQ_5": {
    "use_per_segment_delta0": true,
    "delta0_fallback": 0.0,
    "g": 0.938,
    "L_eff": 2.887,
    "K_us": 0.00289,
    "tau": 0.062
  }
}
```

## Reconstruction quality (substrate signal)

How many agents shipped the right artefacts to be canonically gradable. Failures here are a substrate / contract problem, not a model problem.

| format check | pass | fail |
|---|---|---|
| `agent_folder_exists` | 30 | 0 |
| `has_manifest_json` | 30 | 0 |
| `manifest_parsable` | 30 | 0 |
| `manifest_declares_predict_callable` | 30 | 0 |
| `manifest_declares_platform_support` | 30 | 0 |
| `has_predict_py` | 30 | 0 |
| `has_coeffs_json` | 29 | 1 |
| `has_report` | 16 | 14 |

## Worst-of-cohort (among ok submissions)

**Lowest yaw Δ%**:
- `m1-agent-08` (+40.4%)
- `m2-agent-08` (+46.1%)
- `m1-agent-06` (+46.9%)

**Lowest CTE Δ%**:
- `m1-agent-10` (+49.5%)
- `m1-agent-06` (+52.3%)
- `m1-agent-07` (+53.4%)
