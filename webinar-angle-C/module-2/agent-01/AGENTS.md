# AGENTS.md — webinar-angle-C / module-2 (memory/state)

> **This file is a ratchet.** Every entry below is the encoded form of a real past failure that the team has decided not to re-pay. Read each line. Each is short and orthogonal; together they prevent the most common mistakes on this codebase.

## Project purpose (one paragraph)

Sim-real correlation runtime around the CommonRoad kinematic single-track (KS) vehicle dynamics model. KS is integrated over real openpilot rlog driving data; the predicted lateral state (yaw rate `ψ̇`, lateral acceleration `a_y`) is compared against measured truth channels from the same rlog. The team wants the lateral predictions improved. The longitudinal channel is **not** under test.

## Build / run

`python3` on PATH with `pandas`, `numpy`, `scipy`, `matplotlib`. No venv. The shared `code/` and `data/` are symlinks, read-only by contract. Outputs go to `out/` and `tools/` inside this module. The sim CSVs already exist — do not regenerate.

## Ratchet — accumulated structural constraints

### Sign conventions

1. **Residual sign convention is `pred − meas`.** The `yaw_rate_resid_rads` column in the CSV uses this convention. If you compute residuals by hand, match it (`pred − meas`), not the inverse. *Past failure: a previous agent computed `bias = median(pred − meas)` while assuming `meas − pred` and inverted the ranking of every variant.*
2. **Sign convention is ISO 8855: left-positive.** `δ_road > 0` and `ψ̇ > 0` both correspond to a left turn (CCW about +z). `corr(δ_road, ψ̇_meas)` on cornering samples must be **positive**. If it isn't, you have a sign flip somewhere upstream.

### Steering channel

3. **`delta_road_rad` is what the KS model consumes**, not `delta_wheel_deg`. Confusing the two is a factor-of-~15 error (`i_s ≈ 15-18`). The CSV carries both; pick correctly.

### Platform / truth channels

4. **Tesla has no decodable yaw-rate truth** (the third-party DBC does not decode the IMU). Lateral fidelity scoring must use a Ford platform (Mach-E MK1 or F-150 Lightning MK1). Do not silently fall back to Tesla because it has more segments.

### Operating contract

5. **`v` and `δ` are clamped, not predicted.** Under `clamp_v_to_measured=True, clamp_delta_to_measured=True` in `code/ks_model.py::simulate_ks`. Speed-state agreement is zero by construction and is not the metric. Do not "fix" lateral residuals by unclamping.

### Parameters

6. **Vehicle parameters live in `code/parameters.py::PARAM_BY_PLATFORM`.** Use the dict — do not hand-write `L = 2.875`. The dict values are openpilot-canonical, decoded from each platform's rlog `carParams` event.

### Train / test discipline (the ablation trap)

7. **When fitting a parameter on time-series data, use an interleaved train/test split** (every 5th sample → test) — *not* a contiguous front/back split. The lateral residual is highly autocorrelated; a contiguous split makes the test set systematically different from the train set and over-fits catastrophically. *Past failure: a previous agent used a contiguous 70/30 split and reported a held-out B2 RMSE of 0.73 °/s; an interleaved split reduced it to 0.18 °/s.*

### Per-segment vs per-platform fit discipline

8. **State whether a fit is per-segment or per-platform** in the report. A per-segment fit memorises the segment's sensor offsets and is therefore *calibration*, not a *model improvement*. A per-platform fit generalises (or at least exposes whether the gain generalises). Both are fine, but they must be labelled as such — a per-segment bias correction reported as a 79% improvement is dishonest unless the per-segment caveat is stated alongside.

### Coupled predictions

9. **`a_y_pred = v · ψ̇` is coupled to `ψ̇`.** If you change `yaw_rate_pred_rads`, also re-derive `a_y_pred_mps2` and the residuals — otherwise downstream metrics on `a_y` will be subtly wrong.

### Variant ladder discipline

10. **V0 baseline is `yaw_rate_resid_rads` as-is, no preprocessing.** Any preprocessing (bias removal, smoothing, lag alignment) belongs in V1+, not V0. Folding preprocessing into V0 hides the upgrade that earns it.
11. **All variants must use the same segment set and the same regime mask.** State both explicitly in the report.

### Harness friction

12. **The sub-agent harness blocks `Write` on files matching `(report|findings|summary|analysis).*\.md$`.** You will not be able to write `REPORT.md` directly. Return the report content in your final text response; the orchestrator will persist it.

## What `REPORT.md` must contain

- The platform you scored on, and an explicit statement that `yaw_rate_meas_rads` is **measured**.
- The clamped-vs-predicted statement from rule 5.
- A variant ladder with a fixed accounting scheme (default: strict marginal in V0→V_last order).
- Per-regime RMSE (straight / steady cornering / transient cornering) across every variant row.
- Per-segment vs per-platform fit labels per rule 8.
- Regressions flagged with a physical cause.
