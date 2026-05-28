# Research — lateral-fidelity-challenge

## Operating contract
- KS model in lateral-only mode (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`).
- Only the lateral states (yaw, yaw-rate, a_y, x, y) are *predicted*. v and δ are clamped.
- Ford has measured truth (`yaw_rate_meas_rads`, `a_lat_meas_mps2`); Tesla does not.
- Residual sign convention: `pred − meas` (matches `yaw_rate_resid_rads`).
- ISO 8855 sign convention: left turn → δ_road>0 and ψ̇_meas>0.

## Baselines (V0, evals/baseline_rmse.py)
Mustang Mach-E (315 seg, 913k samples) — overall 0.01613, straight 0.00877, steady 0.03173, transient 0.05680 rad/s.
F-150 Lightning (230 seg, 667k samples) — overall 0.02037, straight 0.00899, steady 0.03617, transient 0.05190 rad/s.

Truth dominates the error in cornering (steady & transient). Straight-line residual is small (~9 mrad/s) — sensor noise floor.

## Failure modes — plausible hypotheses
1. **Static yaw-rate bias** — sensor offset (per-segment) or alignment offset (per-platform). Median(`pred−meas`) ≠ 0 on straights.
2. **Effective steering-gain error** — wrong `i_s` or `L`, or a missing `1 − u·v²` understeer-gradient correction. Manifests as a slope of resid vs `v·δ_road` (the kinematic prediction itself).
3. **Tyre understeer (the kinematic model has none).** At higher `|a_y|`, the kinematic prediction overshoots ψ̇. Manifests as `corr(resid, sign(δ)·|a_y|)` > 0 — i.e., positive resid when turning hard.
4. **Steering-channel time-lag** between `delta_road_rad` and the measured response (rack compliance).

These should be addressed in this order (cheapest → most invasive). Rule 8 (per-segment vs per-platform) applies: bias fits must be reported per-platform to count as model improvement.

## Constraints
- Same segment set & regime mask for V0 and every variant (rule 11).
- Rule 9: a_y_pred = v·ψ̇_pred. Any ψ̇_pred change → rebuild a_y_pred and residuals.
- Use interleaved train/test (every-5th sample) per rule 7.
- Sub-agent harness blocks Write on REPORT.* → return report in chat.
