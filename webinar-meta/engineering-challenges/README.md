# engineering-challenges

The *question of the day* across webinar angles. Each challenge below is fed verbatim to every module agent — the substrate of each module is what differs, not the question.

## The two disciplines

**Naked-prompt discipline** — the prompt names the goal and the deliverable contract, nothing more. No methodology hints, no metric thresholds, no regime catalogue, no scoring procedure. If the prompt does the substrate's job, the angle's claim ("substrate is the leverage") collapses.

**Measurable-success discipline** — every challenge is scoreable post-hoc against domain-grounded metrics, but the rubric lives outside the prompt.

## How to add a new challenge

1. Write the trap catalogue first (privately) — it forces honesty about what the task pressure-tests.
2. Write the success rubric next — each metric must be derivable from the report without re-running the agent.
3. Write the prompt last and *strip*. If you can delete a sentence without making the *goal* ambiguous, delete it.

---

## Challenge 1 — Lateral fidelity

```
We have a kinematic single-track vehicle model that takes measured steering
angle and velocity as inputs and predicts lateral behaviour — yaw rate, and
the trajectory (x, y, heading) that follows by integration.

Baseline (V0) is in `code/ks_model.py`; its predictions are pre-computed as
`yaw_rate_pred_rads` in every `sim.csv`, alongside the truth channel
`yaw_rate_meas_rads`.

Improve the lateral fidelity. You'll be graded on:
  1. Yaw-rate RMSE (rad/s)
  2. Distance-resampled cross-track-error RMSE (m) — your trajectory vs
     truth, sampled at uniform distance.

Whatever harness exists in your working directory (`AGENTS.md`, `skills/`,
helpers) is yours to use, modify, or replace. If nothing is there, build
what you need.

Ship at `final-model/`:
  - `predict.py` exporting `predict(sim_df, platform) -> DataFrame` aligned
    with `sim_df.index`: `yaw_rate_pred_rads` required; `x_m, y_m` optional
    (integrated from yaw_rate + measured v if omitted).
  - `manifest.json` with `platform_support` and `predict_callable`
    (e.g. `"predict.py:predict"`).
  - Any coeffs/scripts your predict depends on.
```

---

## Challenge 2 — Longitudinal closed-loop

```
Our vehicle model currently takes measured longitudinal speed as an input —
that's the crutch we need to remove. Build a longitudinal model that
predicts that channel itself, accurately enough to stand on its own.

You'll be graded on:
  1. Speed RMSE (m/s) — your `v_mps` vs the truth channel.
  2. Per-segment distance error RMSE (m) — integrate your predicted speed
     over each segment, compare to integrated truth speed.

Ship at `final-model/` the same way as the lateral challenge: a `predict.py`
exporting `predict(sim_df, platform) -> DataFrame` aligned with `sim_df.index`
and including a `v_mps` column, a `manifest.json` with `platform_support`
and `predict_callable`, plus any coeffs your predict depends on.
```
