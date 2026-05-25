# Plan — improvements to evaluate

> Phase 2 — locked design. No code yet. Reads `research.md` only.

## Candidate improvements (≥3)

### Candidate A — Understeer-gradient (linear-bicycle) yaw correction

- **Hypothesis (physical):** The kinematic prediction `ψ̇_KS = v/L · tan(δ)` ignores tyre slip. The classical linear-bicycle correction multiplies by `1 / (1 + K_us · v²)` where `K_us = m·(l_r·C_αf − l_f·C_αr) / (L²·C_αf·C_αr)` is the understeer gradient (a function of mass, CG, and per-axle cornering stiffness — all in `parameters.py`). This collapses to KS at low v and softens the yaw response at high v.
- **Signal that suggests it:** F-150 highway slope of 0.447 (model double the truth at 30 m/s) — exactly the symptom of missing understeer. K_us scales with v² → highway hurts most.
- **How to implement:** Post-process the existing CSV columns: compute `ψ̇_pred_corr = ψ̇_pred / (1 + K_us · v²)` with `K_us` computed analytically from the ST parameters already in `code/parameters.py` (no model rewrite). Write new CSV to `out/sim_A/.../sim.csv` with regenerated `yaw_rate_pred_rads`, `yaw_rate_resid_rads`, `a_y_pred_mps2 = v · ψ̇_pred_corr`, `a_y_resid_mps2`. All other columns copied through.
- **Expected effect:** Big drop on F-150 highway (target: RMSE 1.37 → ≤0.7 °/s). Small drop on Mach-E (low speed → v² tiny). Should not make any segment worse.
- **Falsification:** If F-150 highway slope after correction is now <0.8 or >1.2, the K_us magnitude is wrong; if Mach-E urban gets *worse*, the sign convention is wrong.

### Candidate B — Per-segment yaw-rate bias removal

- **Hypothesis (physical):** A near-straight segment with mean residual = +0.7 °/s implies a DC offset on either the measured yaw gyro or the steering-rack zero. Subtracting the per-segment mean residual at low-|δ| samples removes the offset.
- **Signal that suggests it:** Mach-E seg 1 mean residual = +0.012 rad/s (= the entire RMSE on that segment), measured during a stretch where δ stays inside ±0.0025 rad.
- **How to implement:** For each segment, estimate `bias = mean(resid where |δ_road| < 0.005 rad)`, then `ψ̇_pred_corr += bias`. Cap to ±0.03 rad/s (≈1.7 °/s) so we never "correct" a segment where the bias estimate is actually a real cornering signal.
- **Expected effect:** Big drop on Mach-E seg 1 (RMSE 0.70 → ~0.07 °/s). Negligible/none elsewhere.
- **Falsification:** If any segment gets >0.05 °/s *worse*, the bias estimator is being fooled by genuine signal.

### Candidate C — Steering-input lag compensation

- **Hypothesis (physical):** The measured yaw lags the steering input by ~20–80 ms (compliance + sensor pipeline). Shifting predicted forward in time by that lag should align the time series.
- **Signal that suggests it:** Cross-correlation peak at +1 to +4 samples (20–80 ms) on every segment.
- **How to implement:** Shift `ψ̇_pred` forward by the per-platform median lag (estimated by cross-correlation on the segments themselves — risk of in-sample fitting noted).
- **Expected effect:** Modest improvement only — the dominant errors are amplitude (Cand A) and DC (Cand B), and the lag is bounded by ~0.05 rad/s peak signal × 80 ms = ~0.004 rad/s = 0.2 °/s ceiling on what shifting can buy.
- **Falsification:** If the optimum shift on the data differs by more than 2 samples between segments of the same platform, this is overfitting.

## Selected for implementation (1-2)

- **Candidate A (understeer-gradient correction)** — physically principled, deterministic from existing parameters (no fitting), and directly targets the largest residual symptom (F-150 highway slope=0.45). One-line analytical fix.
- **Candidate B (per-segment bias removal)** — orthogonal to A, addresses the Mach-E seg 1 DOMINANT failure mode (constant DC), trivial to layer on top of A.

Candidate C deferred: ceiling on improvement is ~0.2 °/s, and we'd be fitting lag on the same 4 segments we evaluate on. Not worth the noise inside this time budget.

## Pre-committed ablation table (numbers to be filled in Phase 3)

| Variant | Method | Expected RMSE ψ̇ (°/s) — Mach-E | Expected — F-150 |
|---|---|---|---|
| baseline | as-is | 0.42 | 1.06 |
| + A | linear-bicycle understeer correction | ≈0.40 | ≈0.55 |
| + A + B | A then per-segment bias removal at low \|δ\| | ≈0.15 | ≈0.55 |

## Success criterion (lock this)

- **Numerical:** RMSE ψ̇ drops ≥15 % on at least one platform without making the other platform worse by >5 %.
- **Physical:** On the F-150 highway segment, the meas-vs-pred slope moves from 0.45 toward 1.0 (target: 0.8–1.2). On Mach-E seg 1, the mean residual drops by ≥80 %.

## What this plan deliberately does NOT do

- No full Pacejka / nonlinear tyre — overkill for residuals this size, and we have no high-G data.
- No re-decode of CAN — we trust the adapter's outputs as already-flowed through the existing pipeline.
- No re-running of `generate_simdata_ford.py` from `rlog.zst` — too slow, and we can validate the improvement by post-processing the existing CSVs (the KS prediction formula is `ψ̇ = v/L · tan(δ)`, fully reproducible from `v_state_mps` and `delta_state_rad` already in the CSV).
- No editing of `code/` — write a standalone post-processor in `out/`.
- No Candidate C (lag).
