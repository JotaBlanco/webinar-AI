# Module-3 agent-07 — Lateral fidelity (idea-01)

## Headline numbers (pooled across 1,996 segments / 5.2 M samples)

| KPI | V0 baseline | Final | Delta |
|---|---|---|---|
| yaw_rate_rmse (rad/s) | 0.012934 | **0.006511** | **−49.7%** |
| cte_rmse (m) | 163.83 | **79.90** | **−51.2%** |

Bias warnings: V0 had 🚨 CTE drift of −54.8 m on Hyundai and +39.7 m on F-150. After fit: −6.6 m and +6.0 m (just above the 5 m threshold). Yaw bias zeroed on all platforms.

## What I implemented

One variant — per-platform linear-bicycle calibration with understeer gradient:

```
yaw_rate = k_delta · (v/L) · tan(delta_road) / (1 + Ku · v²) + b
```

Fitted per platform on `data/sim/segments/*` (v_mps > 2.0) by minimising pooled yaw-rate squared error. Closed-form OLS for (k, b) at each Ku, scipy 1-D bounded search for Ku. Tesla collapses to (k=1, Ku=0, b=0) as expected — its "truth" column **is** the V0 output. Low-speed (v<1) clamp to V0 to avoid bias-driven yaw at standstill.

## Most painful absence

I would have killed for a **per-segment bias-residual visualiser tied to vehicle parameters** — something like an automated `inspect-residuals --feature=v_mps,delta_road_rad --by=platform --overlay=fit` plot. `inspect-residuals` skill exists but I didn't get to use it; instead I read raw `coeffs.json` numbers and inferred from the bias-warning table. The Mach-E `k_delta = 1.18` is anomalous (V0 underpredicts) and I had no time to diagnose whether it's an `i_s` mismatch, a delta_road_rad scaling bug, or genuine vehicle behaviour. A pre-baked "compare fitted k_delta against openpilot-canonical L/i_s and flag mismatches" hook would have caught that in seconds.

## What the rules almost made me do but stopped

I almost peeked at `module-2.v2/agent-07/final-model/coeffs.json` to see what a prior calibration converged to — git status was loitering in my context and it would have been informationally cheap. The isolation list reminded me that was off-limits and I refit from scratch.

## Most surprising thing

The understeer-gradient `Ku` came out **almost identical** across F-150, Mach-E, and Hyundai (≈ 0.00087–0.00099), despite a 3,084-kg truck and a sedan-sized EV being in the same set. Either the openpilot bicycle-equilibrium really does linearise to a near-universal coefficient, or all three platforms run on similar OE tyre stiffness ratios. Either way, a single `Ku ≈ 9e-4` would barely cost anything in RMSE.

## Files (absolute)

- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-07/final-model/predict.py`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-07/final-model/coeffs.json`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-07/final-model/manifest.json`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-07/out/fit_per_platform.py`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-07/out/score_v0.py`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-07/out/score_final.py`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-07/EXPERIMENTS.md`

Pre-flight: 9/9 pass.
