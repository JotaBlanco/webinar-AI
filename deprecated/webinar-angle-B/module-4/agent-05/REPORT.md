# Module-4 / agent-05 (angle-B) — Lateral fidelity ladder

**Headline.** On 80 Mach-E segments (231 926 samples), only **V1 (per-segment yaw-rate bias) actually improved fidelity** — overall RMSE 0.01190 → 0.01013 rad/s (-15%), driven by a 42% straight-line drop. **V2 (linear-ST prior C_α) regressed by 54%** and V3/V4 added nothing. Net V0→V4 is a regression; the honest answer is "ship V1, do not climb to ST on this fleet without a non-linear-tyre rung."

**Platform & contract.** Scored on `FORD_MUSTANG_MACH_E_MK1` (Ford — measured truth; Tesla excluded). Clamped inputs: `v`, `δ_road`. Predicted output: `yaw_rate_pred_rads`. Verified `yaw_rate_pred_rads ≡ (v/L)·tan(δ)` to 3e-6 rad/s. Sign sanity: `corr(δ, ψ̇_meas) = +0.9087` on cornering.

## Variant ladder (same segments, same regime mask, strict marginal accounting)

| variant | overall | straight | steady | transient | Δ overall |
|---|---:|---:|---:|---:|---:|
| V0 baseline KS | 0.01190 | 0.00853 | 0.02331 | 0.05224 | — |
| V1 per-seg bias | 0.01013 | 0.00498 | 0.02396 | 0.05411 | **-0.00176** |
| V2 lin-ST prior Cα | 0.01656 | 0.01296 | 0.03110 | 0.06191 | **+0.00643** (regression) |
| V3 lin-ST fit Cα | 0.01656 | 0.01296 | 0.03110 | 0.06191 | 0.00000 |
| V4 rate-lead τ | 0.01656 | 0.01296 | 0.03110 | 0.06191 | 0.00000 |

Accounting: strict marginal V0→V4. Sum of marginals = total net drop +0.00467 to floating precision.

## Painful absence

No LOSO ML-residual rung — that was the only rung with a plausible path to closing the steady-cornering residual once ST was eliminated; the 15-min budget did not allow it.

## Near-misses

V3 fit `(C_αf, C_αr)` returned the priors **un-pegged** — the linear-ST objective surface is flat in C_α because residual is dominated by non-C_α-shaped variance (per-segment scatter + high-`|a_y|` slip outside ST validity). V4 `τ* = 0` confirms the CSV is already time-aligned.

## Surprise

The textbook upgrade (KS → linear-ST steady-state gain) regressed by 54%. Mean `|ψ̇_pred|` on cornering (0.1217) was already only 6% under `|ψ̇_meas|` (0.1299); the openpilot prior `K_us = +5.6e-4 s²/m²` further *reduces* gain, widening the gap. **KS-with-clamped-(v,δ) is a stronger lateral baseline than the skill ladder implies**, and the next useful rung is non-linear tyre — not linear-ST.

## Regression flags raised

- V2 shipped as a regression rung with physical reason (wrong prior-K_us sign-of-effect for this fleet).
- V3 zero-improvement flagged as "linear-ST form is wrong, not just the priors".

## RPI artifacts

- `rpi/runs/20260527-155851/research.md`
- `rpi/runs/20260527-155851/plan.md` (locked before implementation)
- `rpi/runs/20260527-155851/implement-notes.md`

Code: `tools/baseline.py`, `tools/variants.py`. Numeric dump: `out/baseline.npz`, `out/variants.json`.
