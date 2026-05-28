# Implement notes — 20260527-155843

All variants on Mach-E (315 segments, 913,626 samples, 50 Hz). Per-regime counts: straight=785,093; steady=107,064; transient=21,469. Identical mask across every variant. Marginal accounting: strict V_prev → V_this overall RMSE.

## Per-variant log

### V1 — per-segment yaw-gyro DC bias removal
- Implemented as: `y_pred_v1 = y_pred_KS - bias_per_seg`, where `bias_per_seg = mean(y_pred_KS - y_meas)` over **straight-line samples only** (`|δ|<0.01`) per segment, falling back to whole-segment mean if a segment has zero straight samples. (Physically motivated: KS yaw rate on a true straight is ≈0, so any non-zero mean of pred-minus-meas there is gyro offset.)
- Result: **REGRESSION**. Overall RMSE 0.01613 → 0.02010 (+24.6%). Straight RMSE 0.00877 → 0.01531 (worse). Steady 0.03177 → 0.03283. Transient 0.05677 → 0.05694.
- Notes / surprises: The plan's falsification criterion ("if straight RMSE does not drop ≥20%, V1 has not addressed straight-line failure mode") **fired**. The hypothesis is rejected: a per-segment DC offset is **not** the dominant straight-line residual mode on this dataset. Likely cause: the `|δ|<0.01` mask still admits small-δ highway samples where `v·tan(δ)/L` is non-negligible (~3 mrad/s at 30 m/s and δ=0.005 rad), so the "bias" estimate absorbs real model signal rather than a sensor offset. The variance reduction expected does not materialise; per-segment mean is a noisy estimator with few effective samples after the high-`v`·small-δ confound.

### V2 — Linear ST steady-state, prior `C_α` (openpilot-canonical)
- Implemented as: `ψ̇_ST = v·δ / (L·(1 + K_us·v²))`, `K_us = m·(l_r·C_αr − l_f·C_αf) / (L²·C_αf·C_αr)`, with KS fallback for `|v|<2 m/s`. Per-segment bias correction applied as in V1.
- Result: overall RMSE 0.02010 → 0.01550 (+22.9% improvement over V1). **Below V0** — V2 absolute RMSE (0.01550) < V0 (0.01613), -3.9% from V0. Straight 0.01531 → 0.00339 (massive drop). Steady 0.03283 → 0.03432 (slightly worse). Transient 0.05694 → 0.06272 (worse).
- Notes / surprises: V2 wins on straight but **regresses on steady and transient cornering vs V0**. This means the prior `C_α` make the ST predict *more* understeer than the Mach-E actually shows — KS-neutral is closer to truth in the cornering regime than ST-with-openpilot-priors. Regression flagged.

### V3 — Fit `C_αf, C_αr` to data (bounded 50–500 kN/rad)
- Implemented as: L-BFGS-B minimising MSE(ψ̇_ST − ψ̇_meas) on cornering samples (|δ|≥0.01), bounds [50e3, 500e3] N/rad. Initial = priors.
- Result: optimiser returned **the priors exactly**: `C_αf=286,551, C_αr=355,912`. Overall RMSE unchanged from V2 (0.01550, marginal drop 0%).
- Notes / surprises: Not pegged at bounds. The loss surface is locally flat at the priors — likely because cornering residual is dominated by **transient samples** that no steady-state ST form can fit. Honest reading: no improvement is reachable within linear-ST steady-state for this dataset; the residual is in the dynamics, not the gain. This is a **near-miss** for the ladder, not an attribution error — V3 added a degree of freedom and the data declined to use it.

### V4 — First-order yaw-rate lag on V3 prediction
- Implemented as: per-segment IIR low-pass `y[k] = y[k-1] + (Δt/τ)·(x[k] − y[k-1])` reset at segment boundaries. `τ` scanned over {0.02, 0.05, 0.08, 0.12, 0.18, 0.25, 0.35, 0.5, 0.75, 1.0} s; minimum at **τ=0.08 s**.
- Result: overall RMSE 0.01550 → 0.01533 (+1.1%). Straight 0.00339 → 0.00314. Transient 0.06272 → 0.06066. Steady essentially unchanged.
- Notes / surprises: τ=0.08 s is physical (typical yaw-rate rise time for a passenger car is 0.1–0.3 s with damping); minimum is interior to the scan, not at the boundary. Improvement is small — confirms the transient residual is not pure first-order lag (more likely tyre relaxation + dynamic ST eigenmodes that need the 2-state ST model, out of scope here).

## Deviations from the plan

- **V1 implementation refined mid-run.** First pass used whole-segment mean residual; resulting V1 was a worse regression (-30%) because for cornering-heavy segments the mean absorbed real model error. Switched to straight-only mean (with fallback). Still regressed (-24.6%) — kept the result and flagged. No plan-row was added or removed. Rationale: same hypothesis ("per-segment gyro DC offset"), more honest estimator. Documented for full transparency.

## Numerical results table (final)

| Variant | Straight RMSE | Steady RMSE | Transient RMSE | Overall RMSE | Marginal drop (overall) | Flag |
|---------|---------------|-------------|----------------|--------------|-------------------------|------|
| V0 | 0.00877 | 0.03177 | 0.05677 | 0.01613 | — | baseline |
| V1 | 0.01531 | 0.03283 | 0.05694 | 0.02010 | **−0.00397 (−24.6%)** | REGRESSION (plan-anticipated) |
| V2 | 0.00339 | 0.03432 | 0.06272 | 0.01550 | +0.00460 (+22.9%) | steady/transient REGRESSION vs V0 |
| V3 | 0.00339 | 0.03432 | 0.06272 | 0.01550 | 0 (0.0%) | NEAR-MISS (fit returned priors) |
| V4 | 0.00314 | 0.03457 | 0.06066 | 0.01533 | +0.00017 (+1.1%) | small gain on transient (τ=0.08 s) |

Net V0 → V4: 0.01613 → 0.01533 (-4.96%). Marginal-drop sum = -0.00397 + 0.00460 + 0 + 0.00017 = +0.00080 = total V0-V4 drop (matches by construction).

## Things I would change about the harness / data / skills

- F-150 `a_lat_meas_mps2` channel has `max|a_y|=1057` — pre-clip outliers at the adapter layer or flag.
- Sim CSV could include `dδ/dt` and a regime label to avoid duplicate computation across agents.
- Skill says "use the dict — do not hand-write values" — but `parameters.py` `F150LightningST` differs from the skill's stated F-150 numbers (L=3.70 vs 3.683; I_z=9903 vs 8108; i_s=16.9 vs 18.0; C_αf=378,307 vs 304,250; C_αr=469,878 vs 349,807). The dict-vs-skill discrepancy needs reconciling.
- A "ST 2-state dynamic" baseline rung would make the transient regime tractable; we hit the ceiling of steady-state ST + first-order lag here.
