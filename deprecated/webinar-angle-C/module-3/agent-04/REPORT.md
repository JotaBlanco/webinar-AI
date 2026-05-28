# Module-3 / agent-04 (angle-C) — Lateral fidelity

## Headline

Lateral yaw-rate RMSE reduced **9.4% on Mach-E** (segment-bias variant) and **18.8% on Lightning** (per-platform affine variant), via a 4-variant ladder under RPI discipline. Surprise: the two Fords disagree on which knob matters — Mach-E is bias-dominated, Lightning is gain-dominated.

## Setting

- **Platform**: FORD_MUSTANG_MACH_E_MK1 (315 segments, 913 626 samples) + FORD_F_150_LIGHTNING_MK1 (230 segments, 667 141 samples).
- **Measured truth**: Ford has `yaw_rate_meas_rads` from CAN; Tesla does not (rule 4 — Tesla excluded).
- **Clamped vs predicted**: `v_mps` and `delta_road_rad` clamped to measured (lateral-only mode); ψ̇ and a_y predicted (rule 5).

## Variant ladder (held-out interleaved every-5th-sample TEST, rule 7)

Mach-E:

| Variant | overall | straight | steady | transient | scope |
|---|---:|---:|---:|---:|---|
| V0 baseline | 0.01613 | 0.00878 | 0.03147 | 0.05744 | — |
| V1 platform bias | 0.01614 | 0.00875 | 0.03155 | 0.05750 | per-platform |
| V2 segment bias | **0.01462** | **0.00507** | 0.03111 | 0.05756 | per-segment (**calibration**) |
| V3 steering gain k=1.110 | 0.01594 | 0.00999 | 0.03024 | **0.05085** | per-platform |
| V4 affine + bias | 0.01579 | 0.00959 | 0.03011 | 0.05214 | per-platform |

Lightning:

| Variant | overall | straight | steady | transient | scope |
|---|---:|---:|---:|---:|---|
| V0 baseline | 0.02037 | 0.00899 | 0.03629 | 0.05161 | — |
| V1 platform bias b=-4.4e-3 | 0.02006 | 0.00799 | 0.03634 | 0.05161 | per-platform |
| V2 segment bias | 0.01938 | 0.00706 | 0.03516 | 0.05128 | per-segment (**calibration**) |
| V3 steering gain k=0.892 | 0.01698 | 0.00786 | 0.02907 | 0.04485 | per-platform |
| V4 affine + bias | **0.01654** | **0.00655** | **0.02883** | 0.04540 | per-platform |

Attribution: strict marginal V0→V1→V2→V3→V4. V2 is **calibration, not model improvement** (rule 8). Honest *model* gain is V3 (per-platform): Mach-E -1.2%, Lightning -16.6%.

## Painful absence

KS has no tire side-slip, so transient residual is fundamentally limited. V3's single gain absorbs rack compliance and understeer at once — no DoF to separate them within KS. Need an ST rung.

## Near-misses / regressions

- V1 on Mach-E flat (gyro-bias hypothesis falsified for that platform).
- V3 worsens **straight** RMSE on Mach-E (0.00878 → 0.00999): k>1 amplifies near-zero δ jitter.
- V4 vs V3 on Mach-E transient regressed (0.05085 → 0.05214): bias term stole variance from gain.

## Surprise

Per-platform gain `k` is **1.110 on Mach-E but 0.892 on Lightning** — opposite signs of correction, even though shipped steer ratios are nearly identical (17.0 vs 16.9). The discrepancy lives in unmodelled rack/tire compliance, not gear ratio.

## RPI artifacts

- `rpi/runs/20260527-160000/research.md`
- `rpi/runs/20260527-160000/plan.md`
- `rpi/runs/20260527-160000/implement-notes.md`

## Eval status

- `evals/baseline_rmse.py`: matched V0 numbers exactly on both platforms.
- `evals/schema_check.py`: PASSED on `out/v4_sample_FORD_MUSTANG_MACH_E_MK1.csv` and `out/v4_sample_FORD_F_150_LIGHTNING_MK1.csv`.
