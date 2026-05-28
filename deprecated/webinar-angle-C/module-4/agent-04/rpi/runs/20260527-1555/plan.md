# Plan — lateral-fidelity-challenge (20260527-1555)

Platforms: FORD_MUSTANG_MACH_E_MK1, FORD_F_150_LIGHTNING_MK1 (only Fords have truth).

Ladder (additive, monotone, fixed order):
- V0 baseline residual `yaw_rate_resid_rads` as-is (skill: baseline-residual).
- V1 per-platform bias removal (median residual on TRAIN).
- V2 lag alignment (best integer shift ±10 samples on TRAIN, ±200ms search).
- V3 steering-gain scalar k on `pred_yaw_rate` (cornering-only LS on TRAIN).
- V4 linear speed-residual model `a + b*v` (TRAIN OLS).

Discipline: interleaved 4:1 train/test (every 5th sample → test). RMSE on TEST.
Same regime mask as baseline-residual. Per-platform fits.

Skills used: baseline-residual, ablation-study (procedure followed, custom runner in `tools/run_ladder.py`).
