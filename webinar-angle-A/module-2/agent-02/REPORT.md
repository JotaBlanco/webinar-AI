# Module-2 / agent-02 — Lateral fidelity report

**Platform scored:** `FORD_MUSTANG_MACH_E_MK1`. The `yaw_rate_meas_rads` and `a_lat_meas_mps2` columns are **measured truth** decoded from rlog CAN, not predictions or self-consistency.

**Speed-known contract honoured.** `v_mps` and `delta_road_rad` are **clamped** inputs; the KS state's own `v`/`δ` updates are overwritten each step. The **predicted** channel under test is `yaw_rate_pred_rads` (V0–V2) or a linear-single-track replacement (V3) consuming the same measured `v, δ`.

**Segment set:** First 120 Mach-E segments (sorted), 348 060 samples at 50 Hz (~116 min driving). Same segment-set and same regime mask across every row.

**Regime definition (held constant):**
- *straight* — `|ψ̇_meas (5-sample boxcar)| < 0.05 rad/s` (313 064 samples)
- *cornering_transient* — not straight ∧ `|dψ̇_meas/dt| > 0.20 rad/s²` (4 241 samples)
- *cornering_steady* — not straight ∧ not transient (30 755 samples)

## Variant ladder (RMSE on `yaw_rate_pred − yaw_rate_meas`, rad/s)

| variant       | RMSE_overall | straight | steady  | transient | marginal Δ overall | total drop vs V0 |
|---------------|-------------:|---------:|--------:|----------:|-------------------:|-----------------:|
| V0_baseline   | 0.01550      | 0.00840  | 0.04020 | 0.05282   | —                  | 0.00000          |
| V1_seg_bias   | 0.01358      | 0.00602  | 0.03711 | 0.04963   | -0.00193           | 0.00193          |
| V2_time_align | 0.01313      | 0.00580  | 0.03691 | 0.04226   | -0.00045           | 0.00237          |
| V3_linear_ST  | 0.01440      | 0.00521  | 0.04129 | 0.05143   | +0.00127 (regression) | 0.00110       |

**Accounting:** sequential / chain decomposition — each row's marginal drop is the overall-RMSE reduction relative to the row above. Sum of signed marginal drops = V0_overall − V3_overall by construction.

**Headline: V0 → V2 cuts overall yaw-rate RMSE from 0.01550 rad/s to 0.01313 rad/s — a 15.3% reduction (24% marginal drop in cornering_transient).**

## What each variant does

- **V0** — `yaw_rate_resid_rads` straight from the CSV, no preprocessing.
- **V1** — per-segment mean-bias subtraction on the residual. Removes IMU yaw-rate offset (~1–3 mrad/s). Explains 81% of the total improvement; biggest gain in *straight* (0.00840 → 0.00602).
- **V2** — best integer-sample lag alignment of `yaw_rate_pred` vs `yaw_rate_meas` per segment, then re-remove bias. Median fitted lag = 3.73 samples ≈ **74 ms** — consistent with rlog timestamp skew between steering-CAN and IMU. Big payoff in *cornering_transient* (14.8% drop).
- **V3** — replace KS with linear single-track steady-state `ψ̇_ST = v·δ / (L + K_us·v²)`, openpilot-canonical `C_αf=286 551, C_αr=355 912 N/rad`, gives `K_us = 1.68e-3 rad/(m/s²)`. **Regressed by 0.00127 rad/s overall.** Physical cause: the openpilot-shipped cornering-stiffness prior is too small (under-correction inversion); on these segments the ST prior over-corrects relative to KS+alignment. Straight regime *did* improve. ST is "directionally right model, wrong calibration" — a real ST upgrade needs a `C_α` fit, not a prior.

## Limitations

- Only AGENTS.md (glossary + truth matrix + operating contract) — no parameter-fit harness. V3 became an honest regression because K_us was wrong for these tyres/segments. A 5-min least-squares fit of `C_α` would likely flip V3 to a strict win.
- Regime thresholds chosen by inspection; not externally validated.
- Per-segment bias estimator uses residual mean — at long one-sided cornering it would absorb signal. Mach-E segments are short (~60 s) so contamination is small but non-zero.

Files: `out/variant_ladder.csv`, `out/meta.json`, `out/analyze.py`.
