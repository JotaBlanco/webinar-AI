# Module 3.v2 — agent-06 lateral fidelity report

**Headline numerical result** (full sim/ scoring, 1996 segments, ~5.2M samples):

| Metric | V0 baseline | Shipped V1 | Improvement |
|---|---|---|---|
| Pooled yaw_rate_rmse | 0.012934 rad/s | **0.005874 rad/s** | −54.6% |
| Pooled cte_rmse | 163.83 m | **56.81 m** | −65.3% |

Per platform (yaw / cte):
- FORD_F_150_LIGHTNING_MK1: 0.00566 / 62.19
- FORD_MUSTANG_MACH_E_MK1: 0.00859 / 98.68 (residual yaw bias −0.0014 → cte_drift −22 m)
- HYUNDAI_IONIQ_5: 0.00766 / 69.53
- TESLA_MODEL_3: 0.00000 / 0.000 (V0 passthrough; no truth)

**What I implemented**
- **V1 (shipped, rung 0)**: KS + linear understeer `yr_ss = v·δ_eff / (L_eff + K_us·v²)` + first-order lag `α = dt/(τ+dt)` + platform-gated per-segment δ₀ estimated from input-only straight-row gate `|yaw_v0|<0.03 ∧ v>5`. δ₀-per-segment ON for Mach-E + IONIQ-5, OFF for Lightning (uses global δ₀). Tesla passthrough. Coefficients are the recipe values from `references/anti-patterns.md` § "Legal cousin".
- **V2 (rejected)**: Nelder-Mead refit of (g, K_us, τ, δ₀) per platform with L_eff pinned to physical wheelbase. Worse than V1 because the recipe's L_eff is deliberately well below physical wheelbase, exploiting g↔L_eff scale invariance to compensate for missing dynamics.
- **V3 (rejected)**: Mach-E coefficient sweep. Residual yaw bias (−0.0014 rad/s) is invariant to (g, K_us) within ±2% → it's a structural artefact, not a calibration error.
- **V4 (rung-1 attempt, rejected, logged)**: Linear dynamic single-track with slip angles, backward-Euler integration, openpilot-canonical (m, Iz, l_f, l_r, C_f, C_r) priors. First explicit-Euler attempt blew up (tyre stiffness ~10× the explicit-Euler stability radius at 20 ms). Backward Euler is stable but yields yaw=0.00864 / cte=69.5 — worse on all three live platforms. The implied steady-state K_us = (m/L²)(l_r/C_f − l_f/C_r) is *smaller* than the rung-0 fit wants; rung 1 would need a joint refit of C_f, C_r per platform — out of budget.

**Most painful absence in this harness**
`fit-model/` — listed in AGENTS.md but not present as a working scaffold. I had to roll my own scipy.minimize loop. That cost the V2 fit going off the rails (pegged at bounds), and meant my rung-1 attempt could not be fit jointly with C_f/C_r as free parameters — I had to ship openpilot priors raw, which is exactly the regime in which rung-1 reliably loses to a tuned rung 0. A model-agnostic fitter with bounds + diagnostics (co-collapse, stuck-on-bound) would have made the rung-1 attempt informative rather than a foregone conclusion.

**What the rules nearly let me do but didn't**
Twice I almost added `a_lat_meas_mps2` as a straight-row detector (recipe muscle memory). The anti-patterns doc and the schema check in score-model both caught it before I committed — the input-only `|yaw_v0|<0.03 ∧ v>5` gate is the legal substitute and works. I also nearly read from `data/sim/` inside `predict()` (where truth is present locally) and would have failed at preflight; the contract clarification in AGENTS.md kept me on `sim_df_agent`-only inputs.

**Most surprising thing learned**
The recipe's L_eff = 2.22 m for Mach-E (vs the physical 2.984 m wheelbase) is not a typo or a bad fit — it's a *deliberate* exploitation of the g↔L_eff scale invariance to compensate for missing transient dynamics. When I "fixed it" by pinning L_eff to the physical wheelbase and refitting, I made things meaningfully *worse*. The kinematic single-track model is best calibrated as a phenomenological shape, not a physical one — and the canonical priors in `code/parameters.py` actively mislead the fitter if you trust them.

**Bundle**
- `final-model/predict.py`, `final-model/coeffs.json`, `final-model/manifest.json`.
- `EXPERIMENTS.md` updated at agent root with V0–V4 entries including the rung-1 attempt.
