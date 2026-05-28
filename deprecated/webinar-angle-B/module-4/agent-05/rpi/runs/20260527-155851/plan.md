# Plan — `rpi/runs/20260527-155851/plan.md`

> Locked before implementation. Fixed segment set (same 80 Mach-E segments), fixed regime mask.

## Variant ladder

| # | Variant | Physical hypothesis | DoF added | Predicted direction | Falsifiable success criterion |
|---|---------|---------------------|-----------|---------------------|-------------------------------|
| V0 | baseline KS prediction (`yaw_rate_resid_rads` as-is) | reference | 0 | — | — |
| V1 | Per-segment yaw-rate bias subtraction, estimated on straight-line samples only and applied to all regimes | The straight-line residual is dominated by a per-trip IMU yaw-gyro offset, not by model error | 1 (constant per segment) | Straight RMSE drops sharply; steady/transient modestly | If straight RMSE drops <30%, hypothesis wrong |
| V2 | Linear ST steady-state gain: replace `(v/L)·tan(δ)` with `v·δ / (L·(1 + K_us·v²))` using openpilot-prior `C_α`. Falls back to KS for `v < 2 m/s` | Understeer gradient `K_us` reduces yaw response in high-`v` cornering, which KS does not model | 1 (functional form, no fit) | Steady-cornering RMSE drops; straight unchanged | If steady RMSE does not drop, K_us is wrong sign or magnitude → ST-prior is wrong for this car |
| V3 | Linear ST with **fit** cornering stiffnesses (`C_αf`, `C_αr`), bounded [50–500] kN/rad, fit on cornering samples only | openpilot priors were measured on sticky OE rubber; this fleet's effective tyre stiffness differs | 2 (`C_αf`, `C_αr`) | Steady + transient RMSE drop further; straight ~unchanged | If fit C_α pegs at the 500 kN/rad upper bound → linear-ST form is wrong, flag regression risk |
| V4 | First-order steering-rate lead: `δ_eff = δ + τ · dδ/dt`, `τ ∈ [0, 0.15] s` fit by line-search on transient-cornering RMSE only | A small actuator/IMU phase offset inflates the transient residual disproportionately | 1 (`τ`) | Transient RMSE drops; steady/straight ~unchanged | If best `τ ≤ 5 ms` or transient RMSE drops <5%, no phase offset to fix |

## Attribution scheme

Strict marginal in fixed order V0→V4: `Δ_n = RMSE(V_{n−1}) − RMSE(V_n)` on the overall-regime metric, recomputed on the **same** sample set. Marginal drops must sum to within 15% of total `RMSE(V0) − RMSE(V4)`. If they don't, double-counting or instability is reported.

## Regime mask (fixed)

- straight: `|δ_road| < 0.01`
- steady cornering: `|δ_road| ≥ 0.01 ∧ |dδ/dt| < 0.05 rad/s`
- transient cornering: `|δ_road| ≥ 0.01 ∧ |dδ/dt| ≥ 0.05 rad/s`

`dδ/dt` computed per segment via `np.gradient`.

## What would invalidate this plan

- Cornering-sign correlation negative (would force a sign-flip rung before any of V1–V4). Already checked: +0.9087. OK.
- V2 with prior `C_α` making things *worse* in steady — would mean K_us has wrong sign for this platform; we ship V2 as a regression rung with physical reason, not silently drop it.
- V3 fit pegs at upper C_α bound → flag regression risk, do not unbound.

## Locked at: 2026-05-27 15:58:51 local
