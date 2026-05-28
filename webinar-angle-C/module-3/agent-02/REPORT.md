# Module-3 / agent-02 (angle-C) — Lateral fidelity

**Platforms.** FORD_MUSTANG_MACH_E_MK1 and FORD_F_150_LIGHTNING_MK1. Tesla excluded — no decodable yaw-rate truth (rule 4).
**Truth channel.** `yaw_rate_meas_rads` (Ford rlog).
**Operating contract.** `clamp_v_to_measured=True`, `clamp_delta_to_measured=True` — only lateral states predicted; `v`, `δ` clamped (rule 5).
**Sign convention.** Residual = `pred − meas` (rule 1); ISO 8855 left-positive confirmed via schema_check.
**Fit scope.** Per-platform (rule 8). Interleaved every-5th-sample train/test (rule 7).

## Variant ladder (test-set RMSE, rad/s)

Mach-E (315 segs, 913 626 samples):

| Variant | overall | straight | steady | transient |
|---|---|---|---|---|
| V0 baseline | 0.01613 | 0.00878 | 0.03147 | 0.05743 |
| V1 +bias | 0.01616 | 0.00875 | 0.03159 | 0.05754 |
| V2 ×gain g=1.0948 | 0.01566 | 0.00981* | 0.02965 | 0.05020 |
| V3 gain+bias | 0.01567 | 0.00977* | 0.02977 | 0.05028 |

Lightning (230 segs, 667 141 samples):

| Variant | overall | straight | steady | transient |
|---|---|---|---|---|
| V0 baseline | 0.02037 | 0.00899 | 0.03629 | 0.05161 |
| V1 +bias b=4.6e-3 | 0.02007 | 0.00800 | 0.03636 | 0.05162 |
| V2 ×gain g=0.8677 | 0.01680 | 0.00764 | 0.02876 | 0.04475 |
| V3 gain+bias | 0.01638 | 0.00638 | 0.02874 | 0.04478 |

## Attribution (additive-bias / multiplicative-gain ladder)

- **V1 bias** captures yaw-rate sensor zero. Negligible on Mach-E (b=1.1e-3); -11% straight on Lightning (b=4.6e-3).
- **V2 gain** captures KS-vs-real lateral-gain mismatch. Dominates: Mach-E -12.5% transient / -5.8% steady; Lightning -21% steady / -13% transient. Sign **flips** between platforms (Mach-E under-predicts, Lightning over-predicts).
- **V3** stacks both; best overall on Lightning, equal to V2 on Mach-E.
- **Regression flagged:** Mach-E V2 straight +11.7% (0.00878 → 0.00981). Physical cause: a multiplicative gain on near-zero ψ̇_pred amplifies the existing straight-line noise floor — exactly the trade-off a gain-only correction should make.

## Coupled re-derivation

After scaling ψ̇_pred, `a_y_pred = v·ψ̇'` and both residual columns were recomputed (rule 9). `evals/schema_check.py` PASS on `out/FORD_MUSTANG_MACH_E_MK1/v3_sample_sim.csv` and `out/FORD_F_150_LIGHTNING_MK1/v3_sample_sim.csv`. `evals/baseline_rmse.py` V0 reproduced exactly.

## RPI artifacts

- `rpi/runs/20260527-160000/research.md`
- `rpi/runs/20260527-160000/plan.md`
- `rpi/runs/20260527-160000/implement-notes.md`
- Variant runner: `tools/run_variants.py`
- RMSE tables: `out/<PLATFORM>/variant_rmse.csv`

## Headline

Per-platform multiplicative gain on ψ̇_pred is the lever; bias is a thin second-order term. Mach-E overall RMSE 0.01613 → 0.01567 (-2.9%), transient -12.5%. Lightning 0.02037 → 0.01638 (-19.6%), transient -13%, straight -29%.

## Painful absence

No tire-slip / yaw-lag term — transient RMSE remains 5-6× straight even after gain. A first-order ψ̇-lag would be V4, deliberately deferred (out of 15-min budget).

## Near-misses

(a) V2 regresses Mach-E straight by 12% — multiplicative gain amplifies noise floor; (b) per-segment fit would have shaved more but is calibration, not model improvement (rule 8).

## Surprise

Gain sign flips between Ford platforms (Mach-E g=1.095 under-predicts; Lightning g=0.868 over-predicts) despite both using canonical openpilot `carParams`. A single global wheelbase/i_s correction would not have worked — fit must be per-platform.

## Eval status

`schema_check.py` PASS on both V3 sample CSVs; `baseline_rmse.py` V0 reproduces canonical numbers.
