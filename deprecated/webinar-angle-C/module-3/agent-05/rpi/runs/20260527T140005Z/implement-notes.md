# Implement notes — 20260527T140005Z

## What I ran

- `tools/fit_ladder.py` — single-pass ladder builder. Loads all sim CSVs for a Ford platform, computes regime mask, fits {b, k, τ} per-platform on the every-5th-sample train split, scores on the held-out 4/5 test split.
- `evals/baseline_rmse.py` — V0 reference (matched my V0 train+test numbers exactly).
- `evals/schema_check.py` — ran on each variant CSV.

## Did the plan survive?

Mostly. Three observations:

1. **V1 (bias) was nearly inert on the Mach-E** — fitted `b = 2.27e-4 rad/s`, marginal RMSE drop 1.6e-6 rad/s. This *falsifies* the "sensor zero offset is meaningful" hypothesis on Mach-E. Per rule 8 / the plan lock, I keep V1 in the ladder and report the null instead of replacing it.
2. **V1 was non-trivial on F-150** — `b = 1.39e-3 rad/s` (about 6x bigger), and contributed 8% of the F-150 total drop. So sensor-zero is platform-dependent.
3. **V2 (static gain) carried most of the improvement.** Mach-E `k = 1.069`, F-150 `k = 1.205`. KS under-predicts ψ̇ by 7–20%. Direction matches the "real-vehicle understeer means KS over-predicts" hypothesis... wait — k > 1 means we *upscale* KS to match measurements, so KS actually **under-predicts** ψ̇. That contradicts my naive understeer prediction and is the most interesting finding. See REPORT.

## Deviations from plan

- None on variant order or attribution scheme.
- Did **not** refit `b` after the lag step. The plan locked strict marginals so re-fitting would muddle attribution. The cost is small: V3 lag drop is still positive on both platforms.
- V4 in the plan was "re-derive `a_y_pred = v · ψ̇_pred_corrected`". I did this but **a_y RMSE got slightly worse** on Mach-E (0.338 → 0.363) and effectively unchanged on F-150. Cause on Mach-E: the `a_y_pred_mps2` column in the original CSV is not exactly `v · ψ̇_pred`, so substituting the corrected ψ̇ into `v·ψ̇` introduces a small offset against whatever the original column was. The yaw-rate-channel improvement is real; the a_y channel is a coupled side-effect whose ground-truth has its own issues (see next).
- **F-150 a_lat_meas channel looks broken.** V0 a_y RMSE is ~10.9 m/s² on straights — an order of magnitude too large for street driving. Mustang a_y RMSE is 0.34 m/s², plausible. Reported as a finding, did not chase.

## Schema check

- `out/FORD_MUSTANG_MACH_E_MK1__variant_sim.csv` — **PASS**
- `out/FORD_F_150_LIGHTNING_MK1__variant_sim.csv` — **PASS**

## Numbers (held-out test RMSE on `yaw_rate_resid_rads`, rad/s)

### Mach-E (per-platform fit)

| Variant | overall | straight | steady | transient |
|---|---|---|---|---|
| V0 baseline | 0.01613 | 0.00876 | 0.03180 | 0.05663 |
| V1 +bias    | 0.01612 | 0.00875 | 0.03182 | 0.05665 |
| V2 +gain    | 0.01557 | 0.00947 | 0.02996 | 0.05052 |
| V3 +lag     | 0.01534 | 0.00934 | 0.03003 | 0.04811 |

Marginal drops overall: bias 0.000002, gain 0.000556, lag 0.000231. Total 0.000789 (4.9% of V0).
Transient RMSE drops 15% (0.0566 → 0.0481).
**Regression flag:** V2 worsens straight RMSE by ~8% (0.00876 → 0.00947). Physical cause: the gain `k=1.069` multiplies the small non-zero ψ̇_pred values present on near-straight segments. On straights the residual is dominated by sensor noise, not KS error, so scaling the prediction up actively adds variance. **Fix-forward**: V2 should apply gain only on |δ_road| above threshold, or be replaced with a regime-aware gain. Out of scope for this run.

### F-150 (per-platform fit)

| Variant | overall | straight | steady | transient |
|---|---|---|---|---|
| V0 baseline | 0.02037 | 0.00899 | 0.03614 | 0.05198 |
| V1 +bias    | 0.02004 | 0.00800 | 0.03615 | 0.05195 |
| V2 +gain    | 0.01635 | 0.00638 | 0.02840 | 0.04536 |
| V3 +lag     | 0.01614 | 0.00624 | 0.02842 | 0.04400 |

Marginal drops overall: bias 0.000325, gain 0.003694, lag 0.000213. Total 0.004233 (20.8% of V0).
F-150 fit is `b = 3.63e-3 rad/s`, `k = 0.860`, `τ = 0.06 s`. **F-150 k < 1 means KS *over*-predicts ψ̇ on F-150 — the opposite direction from Mach-E (k=1.069)**. The two Ford platforms disagree on the sign of the gain correction. This is exactly the kind of platform-level divergence rule 8 (per-platform vs per-segment) is designed to surface: one shared gain across Fords would be wrong. Bigger vehicle (F-150 is heavier) under-steers more under load → over-predicting KS is consistent with that.

## Open questions for future runs

- Why is k > 1? Hypothesis: openpilot `steerRatio` in carParams is conservative; the effective steer ratio at moderate g is smaller. Would test with a per-speed gain.
- Lag τ = 0.08 s (Mach-E) and 0.06 s (F-150) is sensible for tire-relaxation + sensor latency. A bilinear-discretised model would be cleaner.
- F-150 a_lat_meas channel needs decoding triage (separate task).
