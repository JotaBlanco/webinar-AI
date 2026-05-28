# Module-3 / agent-01 (angle-C) — Lateral fidelity

## Headline

Per-platform yaw-rate **scalar gain** is where the lateral fidelity gain hides. On the F-150 Lightning it cuts overall test-set RMSE 19.7% (0.02037 → 0.01636 rad/s). On the Mach-E it cuts 2.8% (0.01613 → 0.01568 rad/s). A per-platform static **bias** is near-null on Mach-E (+1.1 mrad/s) and small on F-150 (+4.6 mrad/s). Bias and gain pull the **opposite direction** between the two Fords — `g_MachE=1.095`, `g_F150=0.867` — so any single workshop-wide multiplier would regress one platform.

## Variants — incremental accounting

TEST split: interleaved every-5th sample (rule 7). Fit on TRAIN only. Per-platform (rule 8). Coupled `a_y_pred = v·ψ̇` recomputed (rule 9). Same segments + regime mask across all variants (rule 11).

| Variant | What | Mach-E ΔoverallRMSE | F-150 ΔoverallRMSE |
|---|---|---|---|
| V0 baseline | `ψ̇_pred` as-shipped | — (0.01613) | — (0.02037) |
| V1 +bias | `ψ̇' = ψ̇ − median(resid_straight)`, per-platform | -0.00002 (no-op) | -0.00030 |
| V2 +bias+gain | `ψ̇'' = g·ψ̇'`, fit on STEADY+TRANSIENT TRAIN | -0.00045 | -0.00371 |
| Total |  | **-0.00045 (2.8%)** | **-0.00401 (19.7%)** |

## Per-regime RMSE (rad/s, TEST set)

Mach-E V0/V2: straight 0.00878/0.00977 (**regression**), steady 0.03147/0.02979, transient 0.05743/0.05029.
F-150 V0/V2: straight 0.00899/0.00636, steady 0.03629/0.02869, transient 0.05161/0.04478.

## Per-segment vs per-platform label

All fits are **per-platform**. Per-segment bias removal explicitly skipped (rule 8 — calibration, not model improvement).

## Regressions flagged with physical cause

- **Mach-E straight regime regresses under V2** (0.00878 → 0.00977 rad/s). Cause: `g=1.095` amplifies near-zero pred-side noise/bias in straights, where the gain's physical motivation (steady-state understeer) doesn't apply. A regime-switched gain would fix it; out of locked scope.
- **Mach-E a_y_pred regresses 0.338 → 0.373 m/s² (coupled refit).** Cause: lateral-G truth carries a calibration offset that the ψ̇-only ladder cannot address. F-150 a_y RMSE ~10 m/s² flags a separate channel-scaling problem, not in scope.

## Painful absence

A model rerun with corrected steering ratio in `parameters.py`. The right place for the gain physically is `i_s` / `L`, but re-running KS over 545 segments was out of budget; the V2 multiplier is mathematically equivalent for `tan(δ)` small but doesn't update `a_y` consistently across all derivations.

## Near-misses

- A steering-lag fit (sub-sample cross-correlation) — would have attacked transient RMSE directly but was deliberately deferred.
- Per-platform `L_eff` instead of `g` — equivalent in the small-angle regime; chose `g` for closed-form linear fit.

## Surprise

The two Fords need **opposite-sign gain corrections**. Mach-E: KS under-predicts yaw rate (real car turns harder than KS — rear-biased mass distribution, rear stiffer than front). F-150: KS over-predicts (heavy truck, soft rubber, column compliance). One model, two platforms, two corrections — the per-platform discipline of rule 8 is the only honest accounting.

## RPI artifacts

- `rpi/runs/20260527-155925/research.md`
- `rpi/runs/20260527-155925/plan.md` (LOCKED, no deviations)
- `rpi/runs/20260527-155925/implement-notes.md`

## Eval status

- `evals/baseline_rmse.py` V0 numbers reproduced inside `tools/lateral_ladder.py` (test-set matches whole-set to 4 d.p.).
- `evals/schema_check.py` on `out/FORD_MUSTANG_MACH_E_MK1/sim_V2.csv` → PASS.
- `evals/schema_check.py` on `out/FORD_F_150_LIGHTNING_MK1/sim_V2.csv` → PASS.
