# KS vs Linear ST — variant catalogue (lateral fidelity)

Reference for the bounded set of legitimate upgrades when improving lateral fidelity on a Ford platform. Order matters: every rung adds *one* degree of freedom and is attributable.

## Background — what KS predicts and what it can't

The CommonRoad **kinematic single-track (KS)** model used in [`code/ks_model.py`](../code/ks_model.py) computes yaw rate as:

```
ψ̇_KS = (v / L) · tan(δ_road)
```

No tyres, no slip, no mass. The wheel just rolls. At low lateral acceleration (≲ 2 m/s²) this is a good approximation; above that the prediction lags because real tyres develop a slip angle that delays the yaw response.

## Variant ladder

### V1 — KS recalibrated

- Pull `L` from `PARAM_BY_PLATFORM` (not hand-written).
- Optionally subtract per-segment yaw-gyro bias on straight-line samples (mean residual where `|δ_road| < 0.01 rad`).
- One degree of freedom added: the per-segment bias.

### V2 — Linear single-track with prior `C_α`

Steady-state linear-bicycle yaw-rate gain:

```
ψ̇_ST = v · δ / (L · (1 + K_us · v²))
K_us = m · (l_r · C_αr − l_f · C_αf) / (L² · C_αf · C_αr)
```

- Parameters from `PARAM_BY_PLATFORM`.
- **Low-speed stiffness.** ST eigenvalues scale as `(C_αf + C_αr) / (m · v)`; they blow up as `v → 0`. Either sub-step the integrator or fall back to KS below `v_min ≈ 2 m/s`. Ford Lightning segments include stationary stretches, so this matters.
- Cornering stiffnesses are openpilot's *prior*, decoded from the rlog `carParams` event.

### V3 — Linear ST with fit `C_α`

Fit `C_αf, C_αr` on the segment set by minimising residual RMSE. Bounded to a physical range (50–500 kN/rad).

- Sensitivity check: if either pegs at the upper bound, the prior is already stiffer than the tyres need; ST may be *worsening* relative to KS at large δ. Report as a regression with cause.

### V4 — residual learner

Small ML model (e.g. ridge regression with features `[v, |a_y|, |δ|, sign(δ̇)]`) trained on V3's residuals.

- **Leave-one-segment-out** cross-validation. In-fold scoring is dishonest and inflates V4's apparent contribution.
- If V4 doesn't beat V3 out-of-fold, ship V3 and call V4 a regression. Partial > faked.

## Contract-violating upgrades (do not use)

- **Unclamping `v` or `δ`** — violates the speed-known contract.
- **Switching the prediction target to `yaw_rate_state_rads`** (the integrator state) — that's a self-consistency channel; the resulting RMSE is structurally smaller and doesn't measure lateral fidelity.
- **Training V4 on the test set** — must use leave-one-segment-out CV.

## Known regression — V2 may worsen V1

On Ford Mach-E the openpilot ST prior is stiffer than the Mach-E tyres want. V1 (KS recalibrated with a steering-ratio / yaw-bias correction) can close most of the steady-state gain, and V2 (ST prior) can give some of it back. This is the workshop's headline finding when it surfaces: the skill makes the agent more *honest*, not more *optimistic*.

## Sign-error checklist

If `corr(δ_road, ψ̇_meas)` is negative on a segment with sustained cornering: you have a sign error. Check the KS-input sign convention (`delta_road_rad = -deg2rad(delta_wheel_deg) / i_s` — the leading minus is intentional, and `i_s` is positive).
