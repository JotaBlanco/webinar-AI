# Implement notes

## What I built

- `out/postprocess.py` — single script, two variants. Reads existing baseline `sim.csv`, recomputes `yaw_rate_pred_rads` / `a_y_pred_mps2` and their `*_resid_*` columns. Writes to `out/sim_A/...` and `out/sim_AB/...` preserving directory layout.
- Variant A: linear-bicycle understeer-gradient correction `ψ̇_corr = ψ̇_KS / (1 + K_us · v²)` with K_us computed from the openpilot-canonical ST parameters in `code/parameters.py`. No fitting.
- Variant B (layered on A): per-segment yaw-rate bias estimated as `mean(resid where |δ_road|<0.005 rad)`, capped at ±0.03 rad/s.

## What happened

### Schema check
Both variant trees pass `evals/schema_check.py` cleanly (8/8 CSVs PASS). The script's residual-sign tolerance (1e-6) is tight enough that I almost shipped a bug here — my first draft of `apply_variant_B` only adjusted `yaw_rate_pred_rads` and `yaw_rate_resid_rads`, forgetting to also recompute `a_y_pred_mps2` and `a_y_resid_mps2`. Without re-deriving them, `a_y_resid != a_lat_meas - a_y_pred` and schema_check would fail. Fixed before first run.

### Baseline reproduction
`evals/baseline_rmse.py` printed:
- Mach-E mean RMSE ψ̇: 0.4155 °/s
- F-150 mean RMSE ψ̇: 1.0607 °/s

These match the numbers research.md cited to four decimals.

### Ablation (mean RMSE ψ̇ in °/s across segments per platform)

| Variant | Mach-E | F-150 | Δ Mach-E | Δ F-150 |
|---|---|---|---|---|
| baseline | 0.4155 | 1.0607 | — | — |
| + A | 0.4149 | 1.0465 | −0.1 % | −1.3 % |
| + A + B | **0.0858** | **0.5992** | **−79.3 %** | **−43.5 %** |

### Per-segment

| Segment | base | A | AB | slope (after A) |
|---|---|---|---|---|
| Mach-E urban (9c2a9c/1) | 0.703 | 0.703 | **0.064** | 0.852 |
| Mach-E urban (0ffbee/12) | 0.128 | 0.127 | 0.107 | 0.877 |
| F-150 highway (a5f419/34) | 1.369 | 1.347 | **0.709** | **0.458** |
| F-150 low-speed (f8fbf5/9) | 0.753 | 0.746 | 0.489 | 0.936 |

### What worked
- Variant B (bias removal) does almost all of the heavy lifting. The two segments where the residual is dominated by a DC offset (Mach-E 9c2a9c/1, F-150 a5f419/34) collapse by ~50–90 %.

### What didn't
- Variant A buys 1–2 % across the board. This was the prediction I had highest physical confidence in, and it's the smallest improvement. **Why:** the openpilot-canonical understeer gradients are tiny — `K_us ≈ 3e-5 s²/m²` for Mach-E and 2.4e-5 for F-150. At 30 m/s the softening factor is only `1 + K_us · 900 ≈ 1.02`. That moves the F-150 highway slope from 0.447 to 0.458, well short of the 0.8–1.2 target in the plan. **The slope-0.45 mystery is not understeer; it's something else** — possibly a steering-ratio mis-specification, a CAN signal scaling issue, or a tyre nonlinearity that's not captured in the linear-bicycle assumption. The 80 ms lag we noted in research.md may also matter more than I gave it credit for. Plan's expected ~0.55 on F-150 with A alone was wrong by a factor of 2x.

### Surprises
- Variant B made the *a_y* residual on Mach-E 9c2a9c/1 *worse* (0.052 → 0.145 m/s²). The yaw-rate bias correction of +0.012 rad/s × v ≈ 8.7 m/s = +0.105 m/s² on `a_y_pred`. Since the original `a_y` residual was small (-0.03), adding +0.105 to the prediction over-corrects. This is the classic tension between fixing one channel and breaking another that's coupled through `a_y = v·ψ̇`.
- F-150 highway slope is the single most striking signal — KS predicts *twice* the real yaw rate, and the canonical understeer correction explains only ~1.5 % of that gap. Something structural is wrong there that this challenge's framing doesn't address.

### Success criterion (from plan.md)
- Numerical: ≥15 % drop on at least one platform, no platform >5 % worse → **MET** (79 % Mach-E, 44 % F-150).
- Physical (a): F-150 highway slope into [0.8, 1.2] → **NOT MET** (still 0.458 after A). Variant B is a DC fix and doesn't change slope.
- Physical (b): Mach-E seg 1 mean resid drops ≥80 % → **MET** (0.012 → ~0.0011 rad/s, 91 %).

## Reproduction

```bash
cd webinar-angle-C/modulo-3
python3 out/postprocess.py both
python3 evals/schema_check.py out/sim_A/segments
python3 evals/schema_check.py out/sim_AB/segments
python3 evals/baseline_rmse.py
python3 evals/baseline_rmse.py out/sim_A/segments
python3 evals/baseline_rmse.py out/sim_AB/segments
```
