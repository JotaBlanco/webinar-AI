# REPORT.md — webinar-angle-E / module-4 / agent-02

## Platform
`FORD_MUSTANG_MACH_E_MK1` (SKILL default; 315 segments; 913,626 rows; cleanest of the two Ford platforms with measured truth).

## Operating contract
- `yaw_rate_meas_rads` is measured truth (gyro).
- `v_mps` and `delta_road_rad` are clamped to measured inputs (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`).
- Speed-state agreement is zero by construction; the only metric is `RMSE(yaw_rate_resid_rads)`.

## Variant ladder (strict-marginal accounting, fixed order V0 → V3)

| Variant | Overall RMSE (rad/s) | straight | steady | transient | Marginal Δ overall | Attribution |
|---|---|---|---|---|---|---|
| V0 baseline (as-is residual) | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — | — |
| V1 KS recalibrated (bias-subtracted) | 0.01469 | 0.00493 | 0.03168 | 0.05730 | **−0.00143** | **+100%** (sole gain) |
| V2 Linear ST, prior C_α | 0.01653 | 0.00701 | 0.03450 | 0.06234 | +0.00184 | **regression** |
| V3 Linear ST, fitted C_α | 0.01663 | 0.00700 | 0.03482 | 0.06266 | +0.00011 | **regression** |

Total drop V0 → V3: **−0.000508 rad/s** (the ladder net-regresses). Sum of marginals matches total drop exactly (accounting is consistent; the 15% tolerance is degenerate when total is negative).

## Wins
- **V1 cuts straight-regime RMSE almost in half** (0.00877 → 0.00493). Per-segment gyro-bias subtraction on straight samples is doing real work — there is a measurable per-segment yaw-gyro offset in this dataset.

## Regression flags (per SKILL: "honest regression flags")
- **V2 worsens every regime vs V1 and vs V0.** Physical reason: openpilot's canonical priors `C_αf = 286,551`, `C_αr = 355,912` N/rad produce a `K_us` that under-rotates the model relative to truth on cornering samples. The ST prior is stiffer than the Mach-E's actual cornering compliance on this segment set.
- **V3 worsens further (marginally) vs V2.** Fit returned `C_αf = C_αr = 150,000` N/rad — **exactly the L-BFGS-B initial guess** — with `pegged=False`. This is *not* the SKILL's anticipated bound-pegging failure; the optimizer stalled on the init, suggesting a flat or non-convex loss surface (likely dominated by the v < 2 m/s KS-fallback region). V3's RMSE is essentially "ST evaluated at the init point."

## Attribution
Strict marginal, fixed-order V0→V1→V2→V3. V1 contributes the entire (negative) net drop; V2 and V3 are regressions. The "additivity to within 15%" check is satisfied trivially because marginals sum to total exactly.

## Phase-attribution (RPI evidence)
- **Phase 1 (Research)** surfaced the transient-regime degeneracy (18 rows for Mach-E) — preventing me from over-weighting transient stats in attribution.
- **Phase 1** also flagged that the straight-regime residual is ~5× smaller than steady — pre-committed me to expect V1 (bias-subtraction) to win on straights, which it did.
- **Phase 2 (Plan-lock)** committed me to running V2/V3 even though Phase-1 stats hinted that bias-fix alone explained most of the structure. Without the lock, I'd likely have stopped at V1, missed the V3-stuck-at-init finding, and reported false confidence in ST.
- **Phase 3 (Implement)** discovered the L-BFGS-B stall — a failure mode the SKILL doesn't enumerate.

## Plan dissent
The locked plan implicitly assumed positive net drop and a meaningful 15%-of-total attribution. In practice the ladder net-regressed and V3's "fit" was a no-op. If re-planning: I'd add a V1.5 (per-segment gyro bias + KS canonical L only, no ST) and a pre-fit gradient probe on V3's loss landscape before trusting `minimize`'s convergence flag. The headline deliverable for the original task ("make lateral predictions better, and tell me how much each change contributed") is: **V1 alone, −8.9% overall RMSE, −44% straight-regime RMSE. V2 and V3 should not ship.**
