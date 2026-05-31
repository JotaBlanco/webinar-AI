# Agent-03 — Lateral Fidelity REPORT

## Headline (full sim/segments, all 4 platforms, 1996 segments / 5.19M samples)

| metric           | V0 baseline | **Final (V1)** | Δ        |
|------------------|------------:|---------------:|---------:|
| yaw_rate_rmse    | 0.012934    | **0.007258**   | −44%     |
| cte_rmse         | 163.83 m    | **79.22 m**    | −52%     |

All bias warnings cleared (V0 had two "🚨" platforms; V1 is `ok` on all).

### Per-platform (Tesla has no independent truth — V0 passthrough by design)

| platform                  | V0 yaw_rmse | V1 yaw_rmse | V0 cte_rmse | V1 cte_rmse | V0 cte_drift | V1 cte_drift |
|---------------------------|------------:|------------:|------------:|------------:|-------------:|-------------:|
| FORD_F_150_LIGHTNING_MK1  | 0.01633     | **0.00670** | 157.5 m     | **70.2 m**  | +39.7 m 🚨   | +4.8 m       |
| FORD_MUSTANG_MACH_E_MK1   | 0.01362     | **0.01236** | 148.0 m     | **129.0 m** | −1.6 m       | −0.6 m       |
| HYUNDAI_IONIQ_5           | 0.01708     | **0.00886** | 247.5 m     | **103.7 m** | −54.8 m 🚨   | −2.3 m       |
| TESLA_MODEL_3             | 0.000       | 0.000       | 0.0 m       | 0.0 m       | 0.0 m        | 0.0 m        |

## What I implemented

**V1 — Kinematic bicycle with understeer-gradient + steering lag + bias trim**, per-platform coefficients:

```
delta_eff[k+1] = delta_eff[k] + dt/(tau+dt) * (delta_road[k+1] − delta_eff[k])
yaw_rate[k]    = v[k] · tan(delta_eff[k] − delta_offset)
                  / (L · (1 + K · v[k]²))
```

Three coefficients fit per platform by Nelder–Mead minimising sample-pooled MSE on `v>2 m/s`:
- `K` (understeer gradient) — captures speed-dependent yaw-gain decay missing from KS.
- `delta_offset` — kills the signed yaw bias that double-integrates into CTE drift.
- `tau` — first-order steering lag (~50–80 ms), improves transient-regime RMSE.

Tesla passes V0 through unchanged: the Tesla `sim.csv` has no independent truth channel (`psi_dot_rads` *is* V0), so any deviation only raises RMSE.

Coefficients (in `final-model/coeffs.json`):
- Lightning : K=1.36e-3, doff=+1.40 mrad, tau=55 ms
- Mach-E    : K=2.70e-4, doff=−0.04 mrad, tau=80 ms
- Ioniq 5   : K=1.48e-3, doff=−0.51 mrad, tau=51 ms

The Mach-E was already mostly tuned at V0 (low K, near-zero bias) — most of the headline improvement comes from Lightning (−55% yaw, −55% CTE) and Ioniq 5 (−48% yaw, −58% CTE), where V0's missing understeer term was producing large signed drift.

## Deliverables

`final-model/predict.py` (exports `predict(sim_df, platform)`), `final-model/coeffs.json`, `final-model/manifest.json`. Pre-flight (`skills/pre-flight-final-model/preflight.py`) passes every functional check; only the REPORT.md presence check is "fail" because the orchestrator will persist this report (sub-agent Write blocks `(report|...).*\.md$`).

## Most painful absent component

**A `cte-first` loss function inside `fit-model/`.** I fit yaw RMSE pooled over samples; yaw fell hard (−44%) and CTE dropped along with it (−52%) but only because the signed yaw bias was the dominant driver. The remaining CTE error is now per-segment route-shape-dependent (worst Hyundai segment still has 274 m signed CTE) — squashing it requires fitting K against the trajectory integral, not the per-sample residual. `fit-model/` exists per AGENTS.md inventory but I didn't load its body; even if I had, fitting through a trajectory integrator within scipy.optimize on 2k segments × 3M samples in the remaining budget felt like the kind of "build the harness" diversion I wouldn't finish. A skill that *already* offered yaw / cte / blend losses as a knob would have removed the calculation/risk of building that glue.

## Rule-prevented near-drifts

I almost reached for the static `parameters.py` priors (`TeslaModel3ST.C_alpha_f` etc.) to compute K from the *dynamic bicycle* understeer-gradient formula `K_us = m/L² · (l_r/Cαf − l_f/Cαr)`. That would have been a cleaner story for the report, but `parameters.py` lives in `code/` which is read-only — and besides, it would have required cornering stiffnesses I didn't trust for Lightning/Ioniq 5 (only Tesla and Mach-E have openpilot-canonical values; Ioniq 5 isn't even in the file I read). Fitting K end-to-end is more honest and the data backed it up.

I also nearly went to `_grade/` to peek at the canonical grader's behaviour for tie-breakers — the isolation list reminded me, didn't go.

## Most surprising thing learned

**A 1.4 mrad steering-zero offset on the F-150 Lightning** — 0.08° at the road wheel — was responsible for +40 m of pooled CTE drift on its own. The yaw-rate effect was a tiny +4 mrad/s mean bias, but because CTE is a double integral of yaw error, that microscopic miscalibration translated into a giant *signed* lateral drift across the cohort. The skill's bias-warning header was right: tune the bias, don't tune the noise. I would have spent the whole 45 minutes chasing tire models if score-model hadn't slapped 🚨 on that row up front.

## Honest failures

- I never used `inspect-residuals`, `visualise-segment`, `compare-models`, `make-train-dev-split`, or `load-segments`. I went straight from "look at residual bias in score output" to "fit K and offset", because the bias signal was unambiguous. Skipping `make-train-dev-split` means my coefficients are fitted on the full set without a held-out dev fold — the canonical grader's split could expose mild overfitting (per-platform 3 params × 2k segments is unlikely to overfit hard, but it's not zero risk).
- Lag (`tau`) improved yaw RMSE (~0.007631 → 0.007258) but did *not* improve CTE (~79.12 → 79.22). I kept it because the yaw gain matters more than the tiny CTE regression at this scale, but on a pure CTE-first scoring it would arguably come out.
- Worst remaining segments are individual Hyundai and Mach-E routes with 200–400 m signed CTE. These are likely sustained-curve segments where the dynamic-bicycle (slip-aware) correction would help; my steady-state K only fixes the *average* gain, not the per-segment phase response.
