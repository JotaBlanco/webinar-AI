# Module-4 / agent-04 (angle-C) — Lateral fidelity ladder

## Headline

Two-platform variant ladder over `yaw_rate_resid_rads` improves overall TEST RMSE by **+1.7%** on FORD_MUSTANG_MACH_E_MK1 (0.01613 → 0.01585 rad/s) and **+18.4%** on FORD_F_150_LIGHTNING_MK1 (0.02037 → 0.01662 rad/s). The dominant lever in both cases is **per-platform steering-gain calibration** (V3). All fits are per-platform on a 4:1 interleaved train/test split. Tesla excluded (no truth channel). Truth = `yaw_rate_meas_rads` (Ford CAN). `v` and `δ` are clamped to measured; KS predicts only lateral states.

## Variant ladder — Mustang Mach-E (TEST, rad/s, n_test=182 725)

| Variant | overall | straight | steady | transient | marginal | scope |
|---|---|---|---|---|---|---|
| V0 baseline (as-is) | 0.01613 | 0.00875 | 0.03162 | 0.05712 | — | per-platform |
| V1 bias removal (b=+0.00075) | 0.01613 | 0.00872 | 0.03170 | 0.05719 | -0.00001 REGRESSION | per-platform |
| V2 lag alignment (-1 sample, -20 ms) | 0.01635 | 0.00886 | 0.03170 | 0.05892 | +0.00021 REGRESSION | per-platform |
| V3 steering gain (k=1.0941) | 0.01590 | 0.00988 | 0.02995 | 0.05195 | -0.00045 | per-platform |
| V4 speed-residual (a=-0.0023, b=+1.1e-4/mps) | 0.01585 | 0.00985 | 0.02984 | 0.05184 | -0.00005 | per-platform |

Attribution coherence: 0.0000 (< 0.15 OK).

## Variant ladder — F-150 Lightning (TEST, rad/s, n_test=133 428)

| Variant | overall | straight | steady | transient | marginal | scope |
|---|---|---|---|---|---|---|
| V0 baseline (as-is) | 0.02037 | 0.00898 | 0.03619 | 0.05186 | — | per-platform |
| V1 bias removal (b=+0.00443) | 0.02006 | 0.00798 | 0.03624 | 0.05186 | -0.00031 | per-platform |
| V2 lag alignment (-1 sample, -20 ms) | 0.02031 | 0.00810 | 0.03631 | 0.05336 | +0.00025 REGRESSION | per-platform |
| V3 steering gain (k=0.8665) | 0.01662 | 0.00648 | 0.02860 | 0.04668 | -0.00368 | per-platform |
| V4 speed-residual (a=-3.9e-4, b=+2.3e-5/mps) | 0.01662 | 0.00649 | 0.02860 | 0.04667 | -0.00000 | per-platform |

Attribution coherence: 0.0000 (< 0.15 OK).

## Regressions (flagged, kept in ladder)

- **V2 lag alignment regresses on both platforms.** Best integer shift on TRAIN is -1 sample, but TEST RMSE worsens. Physical cause: KS is integrated forward over clamped `v, δ` already aligned with `yaw_rate_meas_rads`. There is no real lag — the TRAIN minimum is fitting residual autocorrelation, exactly the failure the interleaved split is designed to catch.
- **V1 bias removal regresses on Mustang** (≈1e-5). Mustang's residual median is ~0.75 mrad/s — sub-noise. F-150's is +4.4 mrad/s (a real sensor zero offset), which is why V1 helps there.

## Painful absence

None. Both `baseline-residual` and `ablation-study` skills covered the ladder. No new skill authored.

## Near-misses / surprise

- **Sign-convention bug in source data.** `yaw_rate_resid_rads` in every `sim.csv` equals `meas − pred`, not `pred − meas` per ratchet rule #1. RMSE is sign-insensitive so V0 is unaffected, but `evals/schema_check.py` FAILS on stock CSVs (max diff 1.4e-1). Anyone using residual *sign* downstream would be inverted. My ladder computes `pred − meas` directly, so attribution signs are correct. **Recommend fixing `code/generate_simdata_ford.py`.**
- **k goes opposite ways on the two Fords:** k=1.094 (Mustang under-predicts ~9%) vs k=0.867 (F-150 over-predicts ~13%). Almost certainly the steering-rack ratio / wheelbase in `PARAM_BY_PLATFORM` is off; truck has the larger error.

## RPI artifacts

- `rpi/runs/20260527-1555/plan.md`
- `rpi/runs/20260527-1555/implement-notes.md`
- `rpi/runs/20260527-1555/ladder_mustang.txt`
- `rpi/runs/20260527-1555/ladder_f150.txt`
- `tools/run_ladder.py`

## Eval status

- `evals/baseline_rmse.py` / `skills/baseline-residual/run.py`: V0 numbers match exactly (Mustang 0.01613, F-150 0.02037).
- `evals/schema_check.py`: **FAIL on stock CSVs** — sign convention bug in `generate_simdata_ford.py`, not introduced by this ladder.

## Skills used / authored

- Used: `skills/baseline-residual/` (V0), `skills/ablation-study/` (procedure). Custom runner `tools/run_ladder.py`.
- Authored: none.
