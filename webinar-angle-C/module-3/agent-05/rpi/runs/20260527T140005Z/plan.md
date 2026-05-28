# Plan — 20260527T140005Z

> LOCKED at 20260527T140005Z. Implementation deviations recorded in implement-notes.md.

## Variant ladder (per-platform fits; FORD_MUSTANG_MACH_E_MK1 primary)

| #  | Variant | Physical hypothesis | DoF added | Predicted direction | Falsifiable success criterion |
|----|---------|---------------------|-----------|---------------------|-------------------------------|
| V0 | baseline | (none — `yaw_rate_resid_rads` as-is) | 0 | — | — (reference) |
| V1 | global bias `b` | yaw-rate sensor / steering-zero offset, per-platform | 1 | reduces straight RMSE most; small effect on transient | straight RMSE drops by ≥ 30% of straight V0; if not, hypothesis falsified |
| V2 | static gain `k` on ψ̇_pred | steer-ratio / KS-gain miscal (k·tan(δ)·v/L) | 1 | reduces steady RMSE more than straight; tiny effect on transient | steady RMSE drops by ≥ 20% relative to V1; corr(resid, v·δ_road) shrinks |
| V3 | first-order lag τ on ψ̇_pred | tire relaxation + sensor latency | 1 | reduces transient RMSE most | transient RMSE drops by ≥ 20% relative to V2; corr(resid, dψ̇_pred/dt) shrinks |
| V4 | re-derive `a_y_pred = v · ψ̇_pred_corrected` | rule 9 — `a_y` is coupled to ψ̇ | 0 (consequence) | `a_y` residual drops proportionally | a_y RMSE drops; schema_check passes |

## Attribution scheme

- Strict marginal in fixed order V0→V4. Marginal drop reported per regime. Sum of marginals expected to be within 15% of total V0→V3 drop (V4 is bookkeeping).
- Fits done on **interleaved every-5th-sample** train (rule 7). Reported RMSE on the **held-out 4/5** test split.
- Per-platform fit (rule 8) — single `(b, k, τ)` triple per platform across all 315 segments.

## Regime mask (fixed, applied identically to every variant)

- straight: `|delta_road_rad| < 0.01`
- steady cornering: `|delta_road_rad| >= 0.01` AND `|dδ/dt| < 0.05`
- transient cornering: otherwise
- Mask computed once on `delta_road_rad` (clamped input, not prediction) so it is identical across variants.

## What would invalidate this plan

- If V1 (bias) eats more than 60% of the transient regime error, the picture is dominated by a constant sensor offset and my V2/V3 hypotheses are mis-framed.
- If `corr(δ_road, ψ̇_meas)` on cornering samples is **negative**, sign convention is broken upstream — bail out and report.

## Locked at: 20260527T140005Z
