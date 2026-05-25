---
name: yaw-bias-correction
description: Detect and remove a constant bias in the yaw-rate residual. The simplest plausible lateral-fidelity improvement — useful as the "is there a free lunch?" first variant before more ambitious work. Per-platform fit.
when_to_use: As ablation variant A in the lateral-fidelity ablation. Always check this before more elaborate fixes — if a constant bias explains most of the residual, the model itself is fine and your real problem is a calibration step upstream.
inputs: Ford sim CSVs (one platform at a time).
outputs: A single scalar bias per platform (rad/s), and modified CSVs with `yaw_rate_pred_rads += bias`, `yaw_rate_resid_rads = meas − new_pred`.
---

# Yaw bias correction — recipe

## Hypothesis

Sensor/coordinate-frame bias or a wheelbase miscalibration shows up as a roughly constant offset in `yaw_rate_resid_rads`. If `mean(yaw_rate_resid_rads) ≠ 0` across many segments, that is a free RMSE win.

## The procedure

1. For each platform, concatenate `yaw_rate_resid_rads` across all available Ford sim CSVs. Compute `bias = mean(yaw_rate_resid_rads)` in rad/s.
2. Apply: `yaw_rate_pred_rads_new = yaw_rate_pred_rads + bias`. Then `yaw_rate_resid_rads_new = yaw_rate_meas_rads − yaw_rate_pred_rads_new`.
3. Recompute RMSE. Expect a drop equal to `sqrt(RMSE_old² − bias²)` if the residual is well-modelled as bias + noise.

## When this *won't* help

- If `corr(pred, meas)` is low — bias correction doesn't fix shape, only offset.
- If `mean(resid) ≈ 0` already — there is no bias to remove.
- If the bias differs *within* a platform across segments — it's not a constant; it's a state-dependent term and you need a richer model.

## Reference implementation

`apply.py` reads a directory of Ford CSVs, computes per-platform bias, writes corrected CSVs to a sibling `out/` dir, prints before/after RMSE.

```bash
python skills/yaw-bias-correction/apply.py data/sim/segments/ out/sim_+bias/
```

## REPORT.md template snippet

```
**Variant: + yaw-bias-correction**
- Mach-E: bias = X.XXXX rad/s → RMSE ψ̇ Y.YY → Z.ZZ °/s (Δ -W%)
- F-150:  bias = X.XXXX rad/s → RMSE ψ̇ Y.YY → Z.ZZ °/s (Δ -W%)
- Interpretation: <bias is calibration / bias is data-dependent / not significant>
```
