# Module-3 agent-09 — Lateral fidelity (idea-01)

## Headline numerical result

Full sim/ dataset, 1996 segments, 5.19M samples:

| metric | V0 baseline | Final (E01) | Δ |
|---|---:|---:|---:|
| yaw_rate_rmse (rad/s) | 0.01471 | **0.00627** | −57% |
| cte_rmse (m)          | 163.83  | **79.45**   | −51% |

Per-platform yaw RMSE: Lightning 0.0163→0.0056, Mach-E 0.0136→0.0089, Ioniq5 0.0177→0.0083. All four signed-bias warnings cleared except a residual −11.6 m CTE drift on Ioniq5.

## What I implemented

- **V0 baseline (E00)**: echo `yaw_rate_pred_rads` from the sim file.
- **E01 (shipped)**: per-platform calibrated kinematic single-track + first-order yaw lag —
  `yr_ss = v·(δ−δ₀)·g / (L_eff + K_us·v²)`, smoothed with `yr[i+1] = yr[i] + (dt/(τ+dt))·(yr_ss − yr[i])`.
  Coefficients `{L_eff, g, δ₀, K_us, τ}` fit by Nelder-Mead on pooled yaw-MSE per platform from sim/. Tesla left at identity (no independent truth channel).

Final model at `final-model/` — preflight passes all 9 checks against the sim-only allowlist contract.

## Most painful absent component

A `fit-trajectory-aware` mode in `fit-model`. The fitter only minimises pooled yaw-MSE; the two KPIs aren't aligned (yaw-RMSE punishes high-frequency noise; CTE punishes sustained low-amplitude bias). Ioniq5 still has a CTE drift even with sub-threshold yaw bias — a CTE-weighted loss could probably squeeze another 10–20 m off CTE without me having to climb a rung.

## Rule-induced near-miss

I almost peeked at `module-3/agent-08/final-model/` from the gitStatus hint, expecting it would already have a calibrated coeffs file I could compare priors against. Stopped because of the isolation rules. That comparison would have probably saved me ~3 minutes of guessing initial `g` magnitudes.

## Most surprising thing

The Lightning's fitted `g = 0.734` (vs my prior of ~0.88). That's a 25%+ scale gap from the workshop's reference value, strongly implying `delta_road_rad` already has *partial* steering-ratio division applied for that platform — different upstream conventions between platforms. The V0 baseline's bias warning on Lightning was telling me exactly that, but I read it as "missing understeer" until I saw the fitted number.

## Files of interest

- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-09/final-model/predict.py`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-09/final-model/coeffs.json`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-09/final-model/manifest.json`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-09/out/fit_per_platform.py`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-09/out/score_final.py`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-09/EXPERIMENTS.md`
