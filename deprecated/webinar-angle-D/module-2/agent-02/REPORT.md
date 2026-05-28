# Lateral fidelity ladder — webinar-angle-D / module-2 / agent-02

Platform: **Ford Mustang Mach-E (MK1)**. `yaw_rate_meas_rads` is the **measured** truth channel (IMU-decoded). 25 of 315 Mach-E segments sampled (seed=42), 72,485 rows. Operating contract: speed- and steering-clamped, lateral-only.

## Headline

**Overall yaw-rate RMSE dropped from 0.01178 rad/s (V0) to 0.00909 rad/s (V1) — a 22.8% reduction.** All subsequent ladder rungs (V2–V4) made things slightly worse on this dataset.

## Variant ladder (RMSE in rad/s)

| Variant | Overall | Straight | Steady | Transient | Δ vs prev | Attribution |
|---|---|---|---|---|---|---|
| V0 baseline (pre-computed resid) | 0.01178 | 0.00913 | 0.02175 | 0.03437 | — | reference |
| V1 KS recalib + per-segment gyro bias | **0.00909** | **0.00498** | 0.02110 | 0.03360 | **−0.00268** | **straight-line gyro bias removal — 100% of total gain** |
| V2 Linear ST, prior C_α | 0.00981 | 0.00307 | 0.02599 | 0.03921 | +0.00072 | helps straights further, hurts cornering (overconfident slip model) |
| V3 Linear ST, fit C_α | 0.00997 | 0.00318 | 0.02640 | 0.03968 | +0.00016 | fit landed at C_αf=C_αr=150k (L-BFGS-B stuck near x0); grid search gives 400k/400k with RMSE 0.01167 — fit gives no meaningful lift over KS |
| V4 Ridge residual learner on V3 | 0.00971 | 0.00336 | 0.02508 | 0.03919 | −0.00026 | LOO oof_rmse=0.00971; recovers a little but cannot undo V2's cornering damage |

Best overall: **V1**. Best on straight regime: **V2**. No variant wins on cornering — all are worse than V0 there.

## Most painful missing component

**`evals/`** — a frozen held-out split with regime-stratified scoring. Without it I had to roll my own segment sampling (seed=42, n=25), bias-correct in-sample, and trust LOO for V4 only. There is no protection against V1's bias-correction overfitting to per-segment quirks, and no way to know whether V2's cornering regression is a real model failure or sampling noise. It cost me ~5 min of redundant diagnostic loops and leaves the ranking confidence-poor.

## What the rules prevented

I almost cross-referenced the Tesla `sim.csv` schema to confirm `yaw_rate_meas_rads` is genuinely absent there (skill claims it is) but `TESLA_MODEL_3/` is under `data/` and the skill is explicit about Ford-only — proceeded on assumption.

## Most surprising thing

**The "ladder" is misnamed.** On Mach-E, the entire correlation improvement comes from removing a per-segment yaw-gyro DC bias on straight-line samples. The linear-ST slip model with both prior and fit C_α gives essentially zero lift over plain KS — because mean |δ_road| ≈ 0.008 rad on real driving data, the slip-angle correction K_us·v²·δ is dwarfed by sensor calibration error. The fit_c_alpha helper looked broken (returned exactly x0), but grid search confirmed it: the loss surface is flat in (C_αf, C_αr) at the priors. The residual-learner rung partially recovers what V2 destroyed but is net-negative vs V1. **Gyro bias > slip dynamics** on this corpus.
