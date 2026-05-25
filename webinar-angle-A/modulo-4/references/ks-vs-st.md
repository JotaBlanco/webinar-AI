---
title: KS vs ST — the lateral fidelity ladder
summary: What lies the KS model tells, in plain language, and what each rung of upgrade (parameter recalibration, KS→ST, C_α tuning, residual ML) is *physically* plugging. The lateral-fidelity-triage skill consumes this as the catalogue of legitimate upgrades.
updated: 2026-05-26
---

# KS vs ST — the lateral fidelity ladder

## What KS models

`ψ̇_KS = (v / L) · tan(δ)`

The car is a rigid rod of length `L`. The front wheel is steered by angle `δ`. Wherever the front wheel points, the car goes. **No tyre**, no slip, no force balance, no mass, no inertia, no cornering stiffness. The yaw rate is purely geometric.

Under the speed-known lateral-only contract the *only* knob KS has to fit reality with is `L` (wheelbase) and the steering ratio `i_s` that converts steering-wheel deg to road-wheel rad.

## Where KS structurally lies

The KS prediction can only be exact when **all three** of the following hold:

1. The tyres are not generating sideslip — i.e. lateral acceleration `|a_y|` is small.
2. The vehicle is in quasi-steady state — i.e. `dδ/dt` and `dv/dt` are small.
3. The steering ratio is the constant that the rlog reports (no compliance, no Ackermann effect, no rear-steer).

Each violation is a *lie* and shows up as residual `ψ̇_pred − ψ̇_meas`. The shape of the residual tells you which lie dominates:

| Regime | Dominant KS lie | Smallest residual would come from |
|---|---|---|
| `straight` (\|ψ̇_meas\| < 0.05 rad/s) | Steering ratio bias, road camber, near-zero δ noise. | Parameter recalibration of `i_s` (and maybe a tiny δ offset). |
| `steady-state cornering` | Tyre slip angles — front and rear wheels are not pointing where they're going. | ST with `C_α` priors → ST with `C_α` fitted. |
| `transient` (\|d ψ̇/dt\| > 0.3 rad/s²) | Yaw inertia `I_z` not present in KS; tyre force ramp-up not modelled. | Full ST with both `m` and `I_z` engaged. |

## The upgrade ladder

### V0 — KS baseline (this is the residual you start with)

What it predicts: `ψ̇ = (v / L) · tan(δ)`. Already computed in the Ford `sim.csv` files (`yaw_rate_pred_rads`).

### V1 — Parameter recalibration

Hold KS structure. Fit `L` and `i_s` against the *measured* yaw rate in `straight` + `steady-state` regimes by minimising RMSE. Do **not** touch `m, I_z, C_α` — KS has none of those.

Physical interpretation: removes static bias in the only two physical scalars KS owns. Typically closes a few percent of overall variance; closes most of the residual in the `straight` regime.

Caveat: if your `L` fit moves more than a couple of cm from the openpilot-canonical value, suspect a sign or units error rather than a real geometric difference.

### V2 — KS → ST (linear single-track with slip angles)

The linear single-track yaw-rate model — also known as the bicycle model with cornering stiffness — adds slip angles `α_f, α_r` and a force balance:

```
α_f = δ − (l_f · ψ̇ + v_y) / v
α_r =     − (l_r · ψ̇ − v_y) / v · (−1)  [signs vary by convention; pick one and stick to it]

F_yf = C_alpha_f · α_f
F_yr = C_alpha_r · α_r

m · (v̇_y + v · ψ̇) = F_yf + F_yr
I_z · ψ̈            = l_f · F_yf − l_r · F_yr
```

Under speed-known lateral-only this collapses to a 2-state linear ODE in `(v_y, ψ̇)` with `v, δ` as exogenous inputs. The steady-state yaw-rate gain has the canonical form

```
ψ̇_ss / δ  =  v / ( L · (1 + K_us · v²) )
```

with the understeer gradient

```
K_us = (m / L²) · ( l_r / C_alpha_f − l_f / C_alpha_r )
```

Physical interpretation: introduces the *missing physics* (slip, mass, inertia, tyre stiffness). Typically closes most of the residual in `steady-state cornering`. The `transient` regime improves but is still bounded by the linearity assumption (no tyre saturation, no relaxation length).

Use the ST parameters already in `code/parameters.py` (`m, I_z, l_f, l_r, C_alpha_f, C_alpha_r`) — they are openpilot-canonical priors, not fits.

### V3 — `C_α` tuning by residual minimisation

Hold ST structure fixed. Fit `(C_alpha_f, C_alpha_r)` by minimising RMSE of `ψ̇_ST(C) − ψ̇_meas` over the same segments. Two scalars; least-squares or a small grid search is fine.

Physical interpretation: the openpilot ST priors assume sticky OE rubber and modest sidewall compliance — your Ford segments may be warmer, colder, or on different tyres. Fitting the priors absorbs that mismatch.

Caveat: a `C_α` fit that pushes either value below ~50,000 N/rad or above ~500,000 N/rad on a passenger car is a sign of overfit (probably absorbing transient/non-linear behaviour into a steady-state parameter). Report the fitted numbers and flag if they look unphysical.

### V4 — Residual ML (optional)

Hold V3 fixed. Fit a small linear regressor (or thin MLP) from `(v, |a_y_meas|, δ, dδ/dt)` to the V3 residual. Train on a subset of segments; evaluate on the held-out subset. With only four Ford segments today, k-fold (leave-one-out) is the honest evaluation protocol.

Physical interpretation: captures the non-linear and transient effects ST misses — tyre saturation, relaxation length, suspension compliance, banked road. A *small* model only, otherwise you are memorising noise.

Caveat: if V4 closes more variance in `straight` than in `transient` you have a leakage problem — the residual ML has learned a feature it shouldn't have access to.

## Out of scope (not legitimate upgrades for this challenge)

- Unclamping `v` or `δ` — breaks the contract.
- Adding a fully non-linear tyre model (Pacejka, Fiala) — outside the catalogue; would be V5.
- Multi-body dynamics, suspension geometry, weight transfer — outside the catalogue; would be V6.
- Switching to a different prediction target (e.g. predicting `a_y` instead of `ψ̇`) — moves the goalpost.

If a residual is still large after V4, the right answer is "we have reached the bottom of this ladder" — not "let me invent a V5."
