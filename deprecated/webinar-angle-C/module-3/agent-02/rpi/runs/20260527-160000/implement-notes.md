# Implement notes

## Run order (locked plan)
1. Load all sim.csv per Ford platform, attach interleaved test mask (row % 5 == 0).
2. Fit V1 bias `b` on train ∩ straight (median).
3. Fit V2 gain `g` on train ∩ cornering (least-squares: g = Σpm / Σp²).
4. Fit V3 incremental bias `b3` on train ∩ straight, post-gain.
5. Score V0..V3 on the test set, per regime.
6. Recompute coupled `a_y_pred = v · ψ̇'` and residuals on a sample V3 sim.csv; run `evals/schema_check.py`.

## Surprise (early-vs-final flip)
- A quick 50-segment peek regressed `pred = a·meas + b` and gave `a = 0.886`, which I initially read as "KS over-predicts by 13 %".
- Fitting the full Mach-E set the other way (gain on `pred` so it matches `meas`) gave `g = 1.095` — KS in fact **under**-predicts yaw rate on Mach-E.
- The two are consistent: `pred = 0.886·meas` ⇔ `meas = 1.129·pred` ≈ g = 1.095 with the LS estimator on noisy data.
- Lesson: on noisy data the two regression directions are not inverses; pick the direction whose residual you actually want to minimise (here: meas − pred), and report the gain you applied to `pred`.

## Direction divergence between platforms
- Mach-E `g = 1.095` (KS under-predicts). Lightning `g = 0.868` (KS over-predicts).
- Same kinematic model, same δ_road convention, opposite gain. Likely cause: per-platform mismatch between the **reported wheelbase / steer-ratio** in `parameters.py` and the **effective** geometry once tire compliance + Ackermann + scrub are folded in. Lightning's higher cornering stiffness and longer wheelbase trade off differently. AGENTS.md rule 6 forbids hand-writing parameters; this is a **calibration-on-top-of-canonical-params** result rather than a parameter rewrite.

## Per-regime attribution (Mach-E)
| Regime    | V0      | V1      | V2      | V3      |
|-----------|---------|---------|---------|---------|
| straight  | 0.00878 | 0.00875 | 0.00981 | 0.00977 |
| steady    | 0.03147 | 0.03159 | 0.02965 | 0.02977 |
| transient | 0.05743 | 0.05754 | 0.05020 | 0.05028 |
| overall   | 0.01613 | 0.01616 | 0.01566 | 0.01567 |

- V1 contribution on Mach-E: ~0 (bias of 1.1e-3 is below the straight-RMSE floor).
- V2 contribution on Mach-E: −12.5 % transient, −5.8 % steady; **regression on straight** (+11.7 %) — a multiplicative gain amplifies the small straight-line noise floor (expected; flagged).
- V3 ≈ V2 (b3 is essentially zero after gain).

## Per-regime attribution (Lightning)
| Regime    | V0      | V1      | V2      | V3      |
|-----------|---------|---------|---------|---------|
| straight  | 0.00899 | 0.00800 | 0.00764 | 0.00638 |
| steady    | 0.03629 | 0.03636 | 0.02876 | 0.02874 |
| transient | 0.05161 | 0.05162 | 0.04475 | 0.04478 |
| overall   | 0.02037 | 0.02007 | 0.01680 | 0.01638 |

- V1 contribution: straight −11 % (sensor offset is real on this truck).
- V2 contribution: steady −21 %, transient −13 %.
- V3 stacks both; best overall, no regressions on Lightning.

## Schema check
- `evals/schema_check.py` PASS on `out/FORD_MUSTANG_MACH_E_MK1/v3_sample_sim.csv`.
- `evals/schema_check.py` PASS on `out/FORD_F_150_LIGHTNING_MK1/v3_sample_sim.csv`.
- Both samples have `a_y_pred = v · ψ̇'` re-derived and `yaw_rate_resid`, `a_y_resid` recomputed to satisfy the coupled-prediction invariant (rule 9).

## Deviations from plan
- None. Ladder ran in locked order. Mach-E straight regression at V2 is flagged (physical cause: a multiplicative gain on near-zero pred amplifies sensor noise).

## Fit scope
- All gains/biases are **per-platform**, not per-segment. Per-segment fits are deliberately out of scope (rule 8: that's calibration, not model improvement).

## Train/test
- Interleaved: train = row % 5 != 0, test = row % 5 == 0. Numbers above are test-set.

## Artifacts
- `tools/run_variants.py` — variant runner.
- `out/<PLATFORM>/variant_rmse.csv` — RMSE table per variant per regime (test set).
- `out/<PLATFORM>/v3_sample_sim.csv` — V3 derived sample sim.csv (one segment) for `schema_check.py`.
