# REPORT — Lateral fidelity of the KS model (Ford platforms)

Module: `webinar-angle-B/modulo-4`. Two Ford platforms, 2 segments each, 50 Hz, ~58 s per segment (5796 rows per platform).

## 1. Baseline residual (as shipped by `code/generate_simdata_ford.py`)

| Platform | N | RMSE psi_dot (deg/s) | bias psi_dot (deg/s) | RMSE a_y (m/s^2) | bias a_y (m/s^2) | corr psi_dot | corr a_y |
|---|---|---|---|---|---|---|---|
| Mach-E | 5796 | **0.5053** | +0.316 | **0.0620** | -0.042 | 0.463 | 0.804 |
| F-150  | 5796 | **1.1045** | -0.873 | **0.4429** | -0.172 | 0.987 | 0.789 |

**Regime structure (F-150).** RMSE psi_dot grows monotonically with both v and |a_y_meas|: low-speed (<5 m/s) 0.53 -> high-speed (>=25 m/s) 1.37; low-G (<1) 1.05 -> high-G (2-3) 2.16. Median ratio meas/pred on real turns (|psi_dot_meas|>2 deg/s) = **0.851** — KS over-predicts yaw by ~15% under cornering, the textbook tyre-compliance gap.

**Regime structure (Mach-E).** Both segments are near-straight-line driving (max |delta_road| = 0.14 deg / 0.31 deg, max |a_y_meas| = 0.38 m/s^2). The model correctly predicts ~zero everywhere; the residual is dominated by **yaw-rate sensor zero-offset**, which is large and segment-specific (seg1 mean +0.700 deg/s; seg2 -0.092 deg/s). Same pattern on F-150 straight-line samples: seg1 mean -1.49 deg/s; seg2 -0.53 deg/s.

## 2. Proposed improvements (six candidates from `tasks/research.md`)

1. **H1 — Per-segment yaw-rate sensor bias correction.** Mechanism: gyro zero-offset drift across power cycles. Signature: straight-line mean residual clearly != 0, varies between segments. Measured by subtracting a robust (median) estimate of the bias from samples with `|delta_road|<0.005 rad` AND `|psi_dot_meas|<0.02 rad/s` AND `v>3 m/s`.
2. **H2 — Full ST (Single-Track Dynamic) with linear cornering stiffness.** Mechanism: lateral force balance, adds sideslip beta as a state. Signature: ratio meas/pred < 1 on turns, gain worsening with v. **Not selected** — too costly inside the time budget.
3. **H3 — Analytic understeer-gradient correction (poor-man's ST).** Mechanism: steady-state portion of ST collapses to a single factor `psi_dot_corrected = psi_dot_KS / (1 + K_u * v^2)` with `K_u = (m / L^2) * (l_r/C_alpha_f - l_f/C_alpha_r)`. Zero new state.
4. **H4 — Steering-compliance lag/filter on delta.** Cross-correlation lag was small (0-4 samples) in this data; deprioritised.
5. **H5 — Wheelbase / steering-ratio recalibration.** Expected ~2-5%, openpilot carParams are usually right.
6. **H6 — IMU-integrated v vs wheel-speed v.** No slipping-wheel events visible.

## 3. Improvements implemented

Two from above (H1, H3) — orthogonal failure modes (bias vs gain).

### H1 — `tools/lateral_corrections.py::estimate_yaw_bias(...)`

Robust per-segment yaw bias via median of straight-line samples:

```python
mask = (np.abs(delta_road_rad) < 0.005) & (np.abs(yaw_meas_rads) < 0.02) & (v_mps > 3.0)
b_hat = float(np.median(yaw_meas_rads[mask]))
yaw_meas_corrected = yaw_meas_rads - b_hat
```

Median (not mean) is robust to occasional turn-onset samples slipping through the mask. Bias is treated as a property of the **measured** channel (sensor zero-offset), not the model.

### H3 — `tools/lateral_corrections.py::apply_understeer_correction(...)`

```python
K_u = (p.m / p.L**2) * (p.l_r / p.C_alpha_f - p.l_f / p.C_alpha_r)
psi_dot_corrected = psi_dot_KS / (1.0 + K_u * v_mps**2)
a_y_corrected = v_mps * psi_dot_corrected
```

Computed K_u values: Mach-E 5.62e-4 s^2/m^2 (factor 1.35 at 25 m/s); F-150 4.53e-4 s^2/m^2 (factor 1.28 at 25 m/s). Both positive (understeer) — consistent with observed F-150 turn-gain 0.851 < 1.

### Driver / evaluator

- `tools/regenerate_with_corrections.py <baseline|h1|h3|h1_h3>` — writes `sim_<variant>.csv` per segment. Reads existing baseline CSV columns (CAN-decode deps unavailable).
- `tools/eval_ablation.py` — aggregates RMSE per platform per variant.

## 4. Ablation table

| Platform | Variant | N | RMSE psi_dot (deg/s) | bias psi_dot (deg/s) | RMSE a_y (m/s^2) | delta psi_dot abs | delta psi_dot % |
|---|---|---|---|---|---|---|---|
| Mach-E | baseline | 5796 | 0.5053 | +0.316 | 0.0620 | +0.0000 | +0.00% |
| Mach-E | +H1      | 5796 | **0.1336** | -0.098 | 0.0620 | -0.3717 | **-73.57%** |
| Mach-E | +H3      | 5796 | 0.5070 | +0.328 | 0.0594 | +0.0017 | +0.34% |
| Mach-E | +H1+H3   | 5796 | **0.1212** | -0.086 | 0.0594 | -0.3840 | **-76.01%** |
| F-150  | baseline | 5796 | 1.1045 | -0.873 | 0.4429 | +0.0000 | +0.00% |
| F-150  | +H1      | 5796 | 0.7770 | -0.424 | 0.4429 | -0.3275 | -29.66% |
| F-150  | +H3      | 5796 | 0.9160 | -0.795 | 0.3223 | -0.1885 | -17.07% |
| F-150  | +H1+H3   | 5796 | **0.5441** | -0.345 | **0.3223** | -0.5604 | **-50.74%** |

Reproducer:
```bash
cd webinar-angle-B/modulo-4
python3 tools/regenerate_with_corrections.py baseline
python3 tools/regenerate_with_corrections.py h1
python3 tools/regenerate_with_corrections.py h3
python3 tools/regenerate_with_corrections.py h1_h3
python3 tools/eval_ablation.py
```

## 5. Ranking of impact

1. **H1 (yaw-bias correction).** Best return on LOC. Wipes 73.6% of Mach-E RMSE (where the model is correct and the residual is mostly sensor zero-offset). On F-150 contributes ~30% by itself. Cost: ~20 LOC, zero risk.
2. **H3 (understeer correction).** Cuts F-150 yaw RMSE by another 17% on top of H1 (a_y RMSE by 27% — v amplifies the correction). Zero benefit on Mach-E (no real cornering). Cost: ~15 LOC.
3. **H1+H3 combined.** Compositionally near-additive (predicted -46.7% from summing single effects on F-150, observed -50.7% — small positive interaction). Best variant on both platforms.

Not selected: H2 (full ST) — likely strictly stronger than H3 but ~120 LOC + integrator stability risk. H4 (steering lag), H5 (param recal), H6 (IMU v) — small expected gains in this data.

## 6. Limitations

- **Only 4 segments total (~6 minutes of driving)**, two of which (Mach-E) are near-straight-line. The Mach-E result is structurally about sensor noise/bias more than model fidelity; a Mach-E corner segment is needed to validate H3 on that platform.
- **CAN-decode deps not installed**, so I reused the existing baseline CSV columns and applied corrections post-hoc rather than re-decoding rlogs. Equivalent for the speed-known lateral-only contract (pred depends only on (v, delta), both in CSV).
- **H1 bias estimator is slightly biased itself.** It takes `median(yaw_meas)` over small-yaw samples, but the model predicts a small non-zero psi_dot on those samples too. Mach-E bias after H1 flipped from +0.32 to -0.10 deg/s. Tightening: subtract model prediction inside the mask before the median. Future work.
- **H3 is steady-state.** Misses transient sideslip dynamics (the proper ST job). On high-rate steering inputs, H3 will under-correct relative to ST.
- **No Tesla coverage** (no decoded yaw-rate truth channel).
- **K_u sign assumes manufacturer cornering-stiffness ratios are right.** Both Ford K_u came out positive (understeer) — consistent with observed turn gain 0.851 < 1, so the sign is right.

## 7. Summary

**Best variant: H1 + H3.** Reduces RMSE psi_dot from 0.505 to 0.121 deg/s (-76.0%) on Mach-E and from 1.104 to 0.544 deg/s (-50.7%) on F-150. RMSE a_y reduced from 0.443 to 0.322 m/s^2 (-27.3%) on F-150. All four ablation variants reproducible via the commands above.
