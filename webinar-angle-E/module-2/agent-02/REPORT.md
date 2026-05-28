# REPORT — lateral-fidelity workflow (workshop scaffold S2)

## Platform and contract

- Platform scored: **FORD_MUSTANG_MACH_E_MK1** (Ford Mustang Mach-E MK1, 315 segments, 913,626 rows).
- `yaw_rate_meas_rads` is measured truth (rlog IMU, Ford-only).
- Speed `v` and steering `δ` are **clamped** to measured under the speed-known operating contract (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). The lateral residual `yaw_rate_resid_rads = yaw_rate_pred − yaw_rate_meas` is the sole metric. No unclamping was attempted.

## Variant ladder

| variant | overall | straight | steady | transient |
|---|---:|---:|---:|---:|
| V0 (baseline KS)               | 0.01613 | 0.00877 | 0.03173 | 0.05680 |
| V1 (KS recalib + per-seg bias) | 0.01469 | 0.00493 | 0.03168 | 0.05730 |
| V2 (Linear ST, prior Cα)       | 0.01653 | 0.00701 | 0.03450 | 0.06234 |
| V3 (Linear ST, fit Cα)         | 0.01663 | 0.00700 | 0.03482 | 0.06266 |

V3 fit result: `C_alpha_f = 1.50e5`, `C_alpha_r = 1.50e5` (= x0), `pegged = False`. L-BFGS-B did not move from initialisation, indicating effectively zero gradient at x0 under the clamped formulation — V3 is not a meaningful refinement of V2 in this run.

## Attribution

Marginal change in **overall** RMSE (negative = improvement):

- V0 → V1 marginal drop: **−0.00144** (−8.9%). Almost entirely from the *straight* regime (0.00877 → 0.00493, −0.00384). The per-segment yaw-gyro bias term is doing nearly all of the V1 work; KS re-derivation from canonical `L` is a small contributor.
- V1 → V2 marginal drop: **+0.00184** (regression of 12.5%). Worsens every regime.
- V2 → V3 marginal drop: **+0.00011** (further marginal regression; fit did not move).
- Sum of marginals: −0.00144 + 0.00184 + 0.00011 = **+0.00051**.
- Total V0 → V3: 0.01663 − 0.01613 = **+0.00050**.
- Sum-of-marginals vs total: agree to within rounding (well within 15%). ✓

## Regressions and physical reasons

- **V2 and V3 regress past V0 overall, and on every regime row.** Per the workflow contract, V3 hitting the upper bound is the named regression flag; here V3 did *not* peg, but it also did not improve over V2, and both sit above V0. I am flagging V2/V3 as a structural regression of the Linear-ST step on this platform.
- Most likely physical causes (workflow does not let me confirm, only hypothesise):
  - The understeer-gradient term `K_us = m·(l_r·C_r − l_f·C_f) / (L²·C_f·C_r)` on the Mach-E is small but **negative-leaning under the openpilot prior** (l_r > l_f, C_r > C_f), pushing ψ̇ in the wrong direction relative to measured yaw under steady cornering — visible as worsening *steady* and *transient* rows.
  - V3's L-BFGS-B starting at (1.5e5, 1.5e5) sat in a flat region of the loss surface — no descent direction found. The fitter is under-specified for clamped-`v`/`δ` data where ψ̇ ≈ (v/L)·tan δ already explains most variance, and the Cα-dependent correction is small relative to gyro bias.
  - V1's straight-regime win confirms a non-trivial **per-segment gyro-bias floor** in the rlog IMU data; until that bias is removed first, ST can only correct around a biased target.

## Notes

- **Tool patch (deviation, recorded):** `tools/step4_run_st_upgrade.py` was broken on first run — it called `P["L"]` on a `MachEST` frozen-dataclass, raising `TypeError: 'MachEST' object is not subscriptable`. I added a minimal `_Bridge` wrapper inside the tool to translate `P["k"]` to `getattr(P, "k")`, with no other change. This is a tool-mechanics fix, not a model change.
- **Workflow honoured:** Steps 1–5 run in order, with the documented flags. No catalogue, no skill, no eval was invoked. No V4 invented. Platform not switched.
- **What I'd want next (out of scope here):** a per-segment audit of `bias` magnitude (is the gyro-bias drive-dependent or vehicle-dependent?); a sign-check on the openpilot Cα prior vs. the road-wheel convention this pipeline uses; and a way to score ST *after* the V1 bias removal, since the current ladder applies bias only inside V1 and discards it for V2/V3 — that ordering may itself be why V2/V3 regress.
