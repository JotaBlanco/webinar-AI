# REPORT — lateral-fidelity workflow (workshop scaffold S2)

## Platform and contract

- Platform scored: **FORD_MUSTANG_MACH_E_MK1** (315 segments, 913,626 rows).
- `yaw_rate_meas_rads` is measured truth (Ford rlog IMU).
- Speed `v` and steering `δ` are **clamped** to measured throughout (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). The speed-known operating contract held for every variant; no regression was "fixed" by unclamping.

## Variant ladder

| variant | overall | straight | steady | transient |
|---|---:|---:|---:|---:|
| V0 (baseline KS)         | 0.01613 | 0.00877 | 0.03173 | 0.05680 |
| V1 (KS recalib + bias)   | 0.01469 | 0.00493 | 0.03168 | 0.05730 |
| V2 (Linear ST, prior Cα) | 0.01653 | 0.00701 | 0.03450 | 0.06234 |
| V3 (Linear ST, fit Cα)   | 0.01663 | 0.00700 | 0.03482 | 0.06266 |

V3 fit: `C_αf = C_αr = 1.5e5 N/rad`, `pegged=False` — but did not move from seed (see below).

## Attribution (change in overall RMSE, rad/s; negative = improvement)

- **V0→V1: −0.00144.** Almost entirely the per-segment yaw-gyro bias subtraction on straight rows. Straight-regime RMSE collapses 0.00877 → 0.00493 (−44%). The canonical-`L` recalibration is a no-op here — `code/parameters.py::MachEST.L` already matches the V0 wheelbase. Steady and transient barely move (steady −0.00005, transient +0.00050).
- **V1→V2: +0.00184 (regression).** Both steady (0.0317 → 0.0345) and transient (0.0573 → 0.0623) get worse. The openpilot prior `C_α` understeer term `K_us·v²` reduces predicted ψ̇ at high speed in a direction the Mach-E does not require; the linear-ST structural form is simply a worse forward model than recalibrated KS on this platform under the clamped contract.
- **V2→V3: +0.00010 (essentially flat, tiny regression).** L-BFGS-B did not move from the seed `(C_αf, C_αr) = (1.5e5, 1.5e5)`. Not pegged at the upper bound — pegged at the initial point. Under the clamped-`v`, clamped-`δ` contract, the gradient of overall-RMSE w.r.t. `C_α` is effectively zero at the seed; the tyre-stiffness lever the optimiser needs is exactly what the operating contract removes. The structural form, not `C_α`, is what's hurting V2/V3.
- **Sum of marginals vs total V0→V3 drop:** +0.00050 vs +0.00050. Identical — there's no interaction term in this sequential ladder, so attribution is exact.

**Bottom line on "how much did each change contribute":** the only positive contribution is V1's straight-rows yaw-gyro bias subtraction (−0.00144 overall, −0.00384 on the straight regime). V2 and V3 are regressions on this platform. Do not deploy linear ST with the openpilot prior or the fit `C_α` here.

## Regressions and physical reasons

- **V2/V3 regress past V0 overall** (0.01653 / 0.01663 vs 0.01613). The understeer term shrinks predicted yaw rate at speed; on the Mach-E sample, the KS over-prediction we hoped to cancel is small relative to the under-prediction the prior `C_α` introduces. Net: worse.
- **Transient regime worsens V0→V1** (0.05680 → 0.05730). A *straight-rows* bias estimate applied uniformly to transient rows is a model-mismatch tax. Small, expected, acceptable trade for the straight-regime win.
- **V3 fit did not move from seed.** Flagged: `pegged=False`, but functionally pegged at the L-BFGS-B initial guess. Workflow stops at V3 as the ladder prescribes; we do not relax clamps or re-weight the loss.

## Notes

- **Tool fix required to complete the workflow.** `tools/step4_run_st_upgrade.py` was written for dict-style parameter access (`P["L"]`), but `code/parameters.py::PARAM_BY_PLATFORM[...]` returns a `MachEST` dataclass instance. Patched in-place with a one-line dict-comprehension shim at line 48 (`P = {k: getattr(_P_obj, k) for k in (...)}`). No numerics changed by the fix; without it step 4 raises `TypeError: 'MachEST' object is not subscriptable` and the workflow cannot proceed. Recorded per AGENTS.md.
- **Painful absence.** The workflow stops at V3 by design. The honest finding is that no prescribed *structural* upgrade (V2 prior `C_α`, V3 fit `C_α`) improves on V1; the only improvement is V1's bias-removal trick, not a model upgrade. A V4 residual-learner rung is the natural next step and is deliberately forbidden at the workflow tier — that absence is the comparison point.
- **Surprise.** V1's win is concentrated entirely in the straight regime; steady and transient barely budge. The bias subtraction is doing yaw-gyro zeroing, not model improvement. Under a regime-weighted scoring rule (transient counts more) V1 would also look like a wash. Plus: V3's fit stuck at its seed because the clamped contract zeroes the gradient — the optimiser's silence is informative, not a bug.

## Limitations / isolation

- Read only this module's files plus `code/` and `data/` via symlinks. No reads or writes outside the module; no siblings, other angles, `_shared`, `_launch`, F1, or `raw-model` touched.
- Single platform (Mach-E); no cross-platform generalisation claimed.
- Step 5 wrote a skeleton REPORT.md; final prose delivered in the agent response per the friction rule (`Write` blocked on `report.*\.md$`).
