# AGENTS.md — webinar-angle-C / module-4 (memory + planning + verification + modularity)

> **This file is a ratchet.** Every entry below is the encoded form of a real past failure. This module adds a fourth and final component: a curated [`skills/`](skills/) library — *modularity*. Skills are procedural recipes loaded metadata-first; you only load a skill body when you invoke it.

## Project purpose (one paragraph)

Sim-real correlation runtime around the CommonRoad kinematic single-track (KS) vehicle dynamics model. KS is integrated over real openpilot rlog driving data; the predicted lateral state is compared against measured truth. The team wants the lateral predictions improved. Longitudinal channel is not under test.

## Build / run

`python3` on PATH with `pandas`, `numpy`, `scipy`, `matplotlib`. No venv. Shared `code/` and `data/` are symlinks, read-only by contract. Outputs go to `out/`, `tools/`, `rpi/runs/`.

## Workflow — RPI

See [`rpi/README.md`](rpi/README.md). Phase artifacts under `rpi/runs/<timestamp>/`.

## Verification — `evals/`

- [`evals/schema_check.py`](evals/schema_check.py) — sim CSV integrity sensor (residual sign + value, sign-convention sanity, NaN-freeness).
- [`evals/baseline_rmse.py`](evals/baseline_rmse.py) — canonical V0 baseline per platform.

## Skills inventory — *load metadata first*

Inspect a skill's frontmatter before loading its body. Skills are *procedural* — they tell you *how* to do a thing. Load when you invoke; otherwise read the description only.

- [`skills/baseline-residual/SKILL.md`](skills/baseline-residual/SKILL.md) — compute the V0 baseline residual on a Ford platform with the canonical conventions (right column, right sign, right regime mask). Use when starting the ladder.
- [`skills/ablation-study/SKILL.md`](skills/ablation-study/SKILL.md) — disciplined ablation procedure: interleaved train/test split, additive monotone variants, strict marginal accounting, regression flagging, attribution-coherence check. Use when running the variant ladder.

If you discover a recurring failure during the run that none of these skills address, **consider authoring a new skill** under `skills/<your-skill-name>/` and citing it in the report. The harness is designed for this — modularity is the lever this module adds.

## Ratchet — accumulated structural constraints (same set as M3)

1. **Residual sign convention is `pred − meas`.** *Past failure: agent computed `bias = median(pred − meas)` while assuming `meas − pred` and inverted every ranking.*
2. **ISO 8855: left-positive.** `corr(δ_road, ψ̇_meas) > 0` on cornering; `schema_check.py` verifies.
3. **`delta_road_rad` is what KS consumes**, not `delta_wheel_deg`.
4. **Tesla has no truth channel.** Use Ford.
5. **`v` and `δ` are clamped, not predicted.**
6. **Parameters in `PARAM_BY_PLATFORM`** — look them up.
7. **Interleaved train/test split**, not contiguous. (The `ablation-study` skill enforces this.)
8. **Label per-segment vs per-platform fits.**
9. **`a_y_pred` is coupled to ψ̇** — re-derive if you change ψ̇.
10. **V0 = `yaw_rate_resid_rads` as-is**, no preprocessing.
11. **Same segment set + same regime mask across variants.**
12. Sub-agent harness blocks `Write` on `(report|findings|summary|analysis).*\.md$` — return REPORT.md content in your final response.

## What `REPORT.md` must contain

Platform; measured-truth statement; clamped-vs-predicted statement; variant ladder with marginal accounting; per-regime RMSE; per-segment/per-platform labels; regressions flagged with physical cause; paths to RPI artifacts; note on `schema_check.py` pass/fail; which skills you used (and whether any new skill was authored).
