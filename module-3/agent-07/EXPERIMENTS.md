# EXPERIMENTS.md

Append-only log of approaches you tried. One entry per concrete attempt. See `references/exploration-discipline.md` for the why.

Schema:

```
## E<NN> — <one-line approach name>
- Hypothesis: why you thought this would help, in one line.
- What I changed vs E<NN-1>: the minimal diff.
- Result (dev): yaw <old> → <new> (Δ%); CTE <old> → <new> (Δ%).
- Verdict: keep | revert | revisit-later.
- Things this rules out: what you learned, even if the experiment failed.
```

Delete this header section once you start logging, but keep the schema close to mind.

---

## E00 — V0 baseline (no changes)
- Hypothesis: establish the floor we're trying to beat.
- What I changed vs nothing: nothing — predict() passes through `yaw_rate_pred_rads`.
- Result (dev): yaw 0.01456; CTE 147.44.
- Verdict: baseline.
- Things this rules out: nothing yet.

## Run 1 — linear-bicycle per-platform calibration (2026-06-01)
Form: `yaw = k_delta * (v/L) * tan(delta_road) / (1 + Ku * v^2) + b`, fit per platform on `data/sim/segments/*` (v_mps>2), pooled-yaw squared error, closed-form (k,b) for fixed Ku + scipy 1-D search on Ku.

Pooled (all platforms):
- yaw_rate_rmse: 0.012934 -> 0.006511 rad/s (-49.7%)
- cte_rmse:      163.83   -> 79.90 m       (-51.2%)

Per platform (yaw rmse | cte rmse):
- FORD_F_150_LIGHTNING_MK1: 0.01633 / 157.5 -> 0.00605 / 63.0  (k=0.937, Ku=0.00087, b=-0.0044)
- FORD_MUSTANG_MACH_E_MK1:  0.01362 / 148.0 -> 0.00910 / 122.0 (k=1.176, Ku=0.00087, b=+0.0002)
- HYUNDAI_IONIQ_5:          0.01708 / 247.5 -> 0.00867 / 108.8 (k=0.944, Ku=0.00099, b=+0.0020)
- TESLA_MODEL_3:            0.00000 / 0.00  -> 0.00000 / 0.02  (k=1.000, Ku=0,        b=0)

Bias warnings: yaw bias zeroed across the board, CTE drift down to <7 m (Hyundai -6.6, F150 +6.0) — both formerly 🚨 are now sub-threshold or just at it.
Pre-flight: 9/9 pass.

Notes:
- Mach-E k_delta=1.18 (>1) is anomalous — V0 underpredicts; could indicate a different L or i_s than openpilot-canonical, or a positive bias in delta_road_rad. Worst-segments on Mach-E are still ≈122 m cte_rmse — there is residual structure (yaw_rmse 0.0091 vs Hyundai 0.0087 on 2.4x fewer samples).
- Tesla is correctly a no-op fit because its truth col IS the V0 output.
- Did not move to ST (linear dynamic single track with slip angles) — the linear-bicycle understeer-gradient form captures the dominant low-frequency v-dependent term that dynamic ST also produces in the linear-tyre limit, and the calibration is fitting data, not parameters from a spec sheet.
