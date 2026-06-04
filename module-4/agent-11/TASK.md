# Task — idea-01 lateral fidelity

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
