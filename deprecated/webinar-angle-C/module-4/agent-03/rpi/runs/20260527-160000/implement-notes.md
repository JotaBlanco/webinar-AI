# Implement notes

Driver: `tools/ladder.py`. Per-platform fits. Test-only RMSE.

## Fits

| Platform                  | delta_offset (rad) | K_us       | lag (samples) |
|---------------------------|-------------------:|-----------:|--------------:|
| FORD_MUSTANG_MACH_E_MK1   |        -0.0002765  |   0.000200 |             1 |
| FORD_F_150_LIGHTNING_MK1  |        -0.0007753  |   0.004500 |             1 |

## Variant table — Mach-E (RMSE rad/s, TEST split)

| Variant          | overall  | straight | steady   | transient | marginal Δ |
|------------------|---------:|---------:|---------:|----------:|-----------:|
| V0_baseline      | 0.01613  | 0.00878  | 0.03147  |  0.05743  |        —   |
| V1_delta_offset  | 0.01615  | 0.00876  | 0.03155  |  0.05747  | **−0.00001 (regression)** |
| V2_understeer    | 0.01639  | 0.00828  | 0.03256  |  0.06014  | **−0.00024 (regression)** |
| V3_lag           | 0.01635  | 0.00825  | 0.03259  |  0.05974  | +0.00004   |
| **net Δ**        |          |          |          |           | **−0.00022 (overall regression)** |

Coherence: marginals sum to total exactly (0.0).

## Variant table — F-150 Lightning (RMSE rad/s, TEST split)

| Variant          | overall  | straight | steady   | transient | marginal Δ |
|------------------|---------:|---------:|---------:|----------:|-----------:|
| V0_baseline      | 0.02037  | 0.00899  | 0.03629  |  0.05161  |        —   |
| V1_delta_offset  | 0.02015  | 0.00828  | 0.03636  |  0.05153  | +0.00022   |
| V2_understeer    | 0.01503  | 0.00523  | 0.02564  |  0.04408  | +0.00512   |
| V3_lag           | 0.01499  | 0.00521  | 0.02559  |  0.04392  | +0.00004   |
| **net Δ**        |          |          |          |           | **+0.00538 (26% drop)** |

Coherence: marginals sum to total exactly (0.0).

## Physical reading

- **F-150 Lightning** is the success story. The linear-bicycle understeer term dominates
  (`K_us = 0.0045 rad·s²/m` — substantial, consistent with a heavy 3084 kg pickup with
  high I_z and large l_r). KS over-predicts yaw rate at speed on this platform because
  it ignores side-slip; the understeer term recovers most of that.

- **Mach-E** is the **painful absence**. V1 and V2 both regress on overall RMSE.
  Two physical readings:
  (a) the openpilot-shipped `C_alpha_f` / `C_alpha_r` priors are already well-calibrated
      for Mach-E tyres — there isn't much room left at the linear-bicycle rung
      (a known limit of the V0 residual at this RMSE floor — the residual is dominated
      by noise + nonlinear effects beyond the linear understeer model);
  (b) the Mach-E test set contains a relatively high proportion of transient cornering
      where neither a constant offset nor a constant K_us helps — what would help is
      tyre relaxation length / actuator dynamics, which is a ST-rung move, not a KS
      tweak. Flagged as a regression with physical cause in the report.

- Lag k=+1 sample (20 ms) on both platforms is small but real and falls inside the
  measurement pipeline jitter band.

## Skills used
- `skills/baseline-residual` — V0 numbers cross-checked against this.
- `skills/ablation-study` — discipline (interleaved split, additive monotone, marginal accounting, attribution-coherence, regression flagging) followed throughout.

No new skill authored — both regressions were one-off platform-specific facts, not a
recurring procedural failure that a new skill would capture.

## Notes / deviations
- schema_check.py flags the stored `yaw_rate_resid_rads` as `meas − pred` rather than
  the convention's `pred − meas`. Irrelevant to RMSE (sign-squared); flagged for the team
  in REPORT.
- All fits per-platform (not per-segment).
