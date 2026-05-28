# Module-2 / agent-03 (angle-C) — Lateral fidelity ladder

## Headline

On 315 Mach-E segments, the lateral-yaw-rate ladder went from RMSE 0.924 deg/s (V0) → 0.879 deg/s (V3) on a held-out interleaved test set — a 4.9% global cut, driven almost entirely by an 80 ms time-alignment and a +8.5% steering-gain scaler. Bias removal was a wash.

## Variants (strict marginal, V0→V3, per-platform fits)

| Variant | all | straight | steady | transient |
|---|---:|---:|---:|---:|
| V0 baseline (`yaw_rate_resid_rads` as-is) | 0.9242 | 0.4776 | 1.3386 | 2.6357 |
| V1 + bias (median pred-meas on train-straight = +0.00127 rad/s) | 0.9260 | 0.4753 | 1.3451 | 2.6424 |
| V2 + lag (median 4 samples = 80 ms, per-segment, train-half xcorr) | 0.9112 | 0.4679 | 1.3452 | 2.5535 |
| V3 + steering-gain k=1.0848 (per-platform LS, cornering-train) | **0.8787** | 0.5048 | 1.3370 | **2.2155** |

Marginal Δ on RMSE_all (deg/s, % of V0):
- V1 bias: -0.002 (-0.2%) — negligible
- V2 lag: +0.015 (+1.6%)
- V3 gain: +0.033 (+3.5%)

Total improvement V0→V3: **0.046 deg/s = 4.9% of baseline**; on the transient regime the improvement is **16%**.

Train/test discipline: every-5th-sample interleaved split (rule 7). All variants share segment set and regime masks. Bias and gain are **per-platform** fits; lag is **per-segment**. Platform: **FORD_MUSTANG_MACH_E_MK1** (`yaw_rate_meas_rads` is measured truth, IMU-decoded; `v`, `δ` clamped to measured, only lateral states predicted per rule 5). Sign check: `corr(δ_road, ψ̇_meas) = +0.702` on cornering — ISO 8855 holds.

## Painful absence

A KS model with no tyre slip cannot reproduce the **transient phase lag** between steering input and yaw rate — that's exactly the 80 ms shift V2 recovers. The model also under-predicts yaw amplitude by ~8% across the platform (V3's k=1.085) — consistent with KS assumption of zero slip angle at the rear axle understating gain at the speeds in this fleet.

## Near-misses

- Per-platform median bias was only 0.00127 rad/s (0.073 deg/s) — well below the straight-line noise floor, so V1 didn't help. A per-segment bias would have looked huge but is calibration, not improvement (rule 8).
- Tesla has more segments but no decodable yaw truth (rule 4) — would have silently scored noise.

## Surprise / regression

**V3 regresses on the straight regime** (0.468 → 0.505 deg/s, +0.037). Physical cause: scaling pred by k=1.085 also amplifies the integrator's small straight-line drift, where there is no real signal to gain-match against. A regime-gated gain (apply k only when |δ_road| > 0.005) would dominate V3, but I kept V3 single-knob per rule 11 (same mask across regimes). I did **not** re-derive `a_y_pred = v·ψ̇` for the new yaw — flagged for rule 9; the next ratchet step.

Files: `tools/ablate.py`, `out/variant_ladder.csv`.
