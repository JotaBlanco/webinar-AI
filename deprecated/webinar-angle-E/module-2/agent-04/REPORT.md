# REPORT — lateral-fidelity workflow (workshop scaffold S2)

## Platform and contract

- Platform scored: **FORD_MUSTANG_MACH_E_MK1** (Mach-E MK1; 315 segments, 913,626 rows).
- `yaw_rate_meas_rads` is measured truth from the rlog IMU (Ford-only — no Tesla measured yaw available).
- Speed `v` and steering `δ` are clamped to measured (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Lateral residual `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` is the sole metric. No unclamping was attempted.

## Variant ladder

| variant | overall | straight | steady | transient |
|---|---:|---:|---:|---:|
| V0 (baseline KS, openpilot canonical) | 0.01613 | 0.00877 | 0.03173 | 0.05680 |
| V1 (KS recalib + per-segment yaw-gyro bias) | 0.01469 | 0.00493 | 0.03168 | 0.05730 |
| V2 (Linear ST, openpilot-prior Cα) | 0.01653 | 0.00701 | 0.03450 | 0.06234 |
| V3 (Linear ST, L-BFGS-B fit Cα) | 0.01663 | 0.00700 | 0.03482 | 0.06266 |

V3 fit: Cα_f = Cα_r = 150_000 N/rad (= x0). `pegged=False`. The optimizer never moved from initialisation.

## Attribution (overall RMSE, lower = better)

- V0→V1 marginal: **+0.00144 improvement** (8.9% relative). Almost entirely from straight regime (0.00877 → 0.00493, −44%). Steady and transient are unchanged or fractionally worse, confirming the win is gyro bias, not vehicle dynamics.
- V1→V2 marginal: **−0.00184 regression** (every regime worsens). The understeer-corrected ST `psi = v·δ / (L·(1 + K_us·v²))` returns smaller yaw than KS, and the bias correction from V1 is not carried forward by design.
- V2→V3 marginal: **−0.00010 regression** (essentially identical to V2). L-BFGS-B stalled at the init Cα; the loss is flat at x0 under the current clamps, so "fit Cα" is a misnomer here.
- Sum of marginals (−0.00050) equals total V0→V3 drop (−0.00050). Variants are not compounded — V2/V3 are computed from raw KS form, not from V1 — so the equality is bookkeeping, not a coincidence.

## Regressions and physical reasons

- V2 and V3 both regress vs V0 in **every** regime (overall, straight, steady, transient).
- Physical reading: openpilot's Mach-E Cα (286,551 / 355,912 N/rad) plus 2,336 kg mass yield a small understeer gradient `K_us ≈ m·(l_r·C_r − l_f·C_f)/(L²·C_f·C_r)` that shaves a few percent off the KS-predicted yaw. KS already over-predicts straight-line yaw (that's what the V1 bias correction shows), so multiplying by `1/(1+K_us·v²)` makes it slightly smaller — but the bigger problem, the un-removed straight-line gyro bias, dominates. ST without bias removal is worse than KS with bias removal.
- V3 not pegged but unmoved — the loss surface around x0 is flat enough that L-BFGS-B converges immediately. With most rows being straight (785,093 of 913,626 ≈ 86%), the yaw signal that Cα can influence is tiny relative to the bias-dominated residual.

## Notes — deviations and absences

- **Tool fix recorded.** `tools/step4_run_st_upgrade.py` accessed `PARAM_BY_PLATFORM[platform]` with dict subscripting (`P["L"]`), but the parameters module returns frozen dataclasses (`MachEST(...)`). Added a small `_AttrDictView` adapter inside the script so `P["L"]` returns `getattr(obj, "L")`. No physics or numerics changed. Recorded as workshop signal per AGENTS.md's "do not deviate, record deviation" clause.
- **Ladder caps at V3.** Per AGENTS.md, no V4 residual learner is permitted in this workflow tier, even though V1's bias-removal pattern strongly suggests a per-segment residual model would beat all three ST variants. Painful absence: cannot port V1's bias correction into V2/V3 to test whether ST helps once bias is gone.
- **Single platform.** No room to switch to F-150 Lightning to cross-check whether ST's regression is Mach-E-specific (mass and rear-bias) or general.
- **V3 honesty.** With pegged=False but Cα at x0, V3 is functionally a tied repeat of V2 at the init point, not an independent fit. Treat it as such.
- **Headline recommendation if forced to pick one:** ship V1. Reject V2/V3 on this dataset.
