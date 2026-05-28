# AGENTS.md — webinar-angle-C / module-3 (memory + planning + verification)

> **This file is a ratchet.** Every entry below is the encoded form of a real past failure that the team has decided not to re-pay. Read each line. This module also adds two new components: a **planning** discipline (RPI loop, see [`rpi/README.md`](rpi/README.md)) and a **verification** budget ([`evals/`](evals/)).

## Project purpose (one paragraph)

Sim-real correlation runtime around the CommonRoad kinematic single-track (KS) vehicle dynamics model. KS is integrated over real openpilot rlog driving data; the predicted lateral state is compared against measured truth. The team wants the lateral predictions improved. Longitudinal channel is not under test.

## Build / run

`python3` on PATH with `pandas`, `numpy`, `scipy`, `matplotlib`. No venv. Shared `code/` and `data/` are symlinks, read-only by contract. Outputs go to `out/`, `tools/`, and `rpi/runs/`.

## Workflow — RPI (Research → Plan → Implement)

Do not open the task and start coding. Break the work across three explicit phases using the templates in [`rpi/templates/`](rpi/templates/) and write each phase's artifact into [`rpi/runs/<timestamp>/`](rpi/runs/) before moving on. See [`rpi/README.md`](rpi/README.md). The phase artifacts are part of the deliverable.

## Verification — `evals/`

Computational sensors. Run them. Each is fast and deterministic. They are how this module makes results auditable.

- [`evals/schema_check.py`](evals/schema_check.py) — verifies sim CSV integrity (residual sign, residual value within 1e-6, sign-convention sanity via `corr(δ_road, ψ̇_meas) > 0`, NaN-freeness, required columns present). Run on every variant CSV before scoring.
- [`evals/baseline_rmse.py`](evals/baseline_rmse.py) — canonical V0 baseline RMSE per platform, broken out by regime. If your "before" RMSE doesn't match this, your scoring code has a bug.

## Ratchet — accumulated structural constraints

### Sign conventions

1. **Residual sign convention is `pred − meas`.** The `yaw_rate_resid_rads` column uses this. If you compute residuals by hand, match it. *Past failure: a previous agent computed `bias = median(pred − meas)` while assuming `meas − pred` and inverted the ranking of every variant.*
2. **ISO 8855: left-positive.** `δ_road > 0` and `ψ̇ > 0` both correspond to a left turn. `corr(δ_road, ψ̇_meas)` on cornering samples must be positive. (`evals/schema_check.py` verifies this.)

### Steering channel

3. **`delta_road_rad` is what KS consumes**, not `delta_wheel_deg`. Factor-of-~15 error otherwise.

### Platform / truth channels

4. **Tesla has no decodable yaw-rate truth.** Use Ford. Do not silently fall back to Tesla because it has more segments.

### Operating contract

5. **`v` and `δ` are clamped, not predicted** under `clamp_v_to_measured=True, clamp_delta_to_measured=True`. Speed-state agreement is zero by construction.

### Parameters

6. **Vehicle parameters live in `code/parameters.py::PARAM_BY_PLATFORM`.** Use the dict — do not hand-write.

### Train / test discipline

7. **Use interleaved (every-5th-sample) train/test split**, not contiguous. Lateral residuals are autocorrelated; contiguous splits over-fit catastrophically. *Past failure: agent reported held-out B2 RMSE of 0.73 °/s with contiguous split; interleaved gave 0.18.*

### Per-segment vs per-platform fit

8. **State whether a fit is per-segment or per-platform.** Per-segment fits memorise sensor offsets — that's calibration, not model improvement. Per-platform fits expose whether the gain generalises.

### Coupled predictions

9. **`a_y_pred = v · ψ̇` is coupled to ψ̇.** If you change yaw rate, re-derive `a_y_pred` and the residuals. (`evals/schema_check.py` catches this if you forget.)

### Variant ladder discipline

10. **V0 baseline = `yaw_rate_resid_rads` as-is, no preprocessing.** Preprocessing belongs in V1+.
11. **Same segment set + same regime mask across every variant.**

### Harness friction

12. The sub-agent harness blocks `Write` on `(report|findings|summary|analysis).*\.md$`. Return REPORT.md content in your final response.

## What `REPORT.md` must contain

- Platform; measured-truth statement.
- Clamped-vs-predicted statement.
- Variant ladder with named accounting scheme.
- Per-regime RMSE (straight / steady / transient).
- Per-segment vs per-platform labels per rule 8.
- Regressions flagged with a physical cause.
- Paths to the three RPI artifacts under `rpi/runs/<ts>/`.
- A note on whether `evals/schema_check.py` passed on your variant CSV(s).
