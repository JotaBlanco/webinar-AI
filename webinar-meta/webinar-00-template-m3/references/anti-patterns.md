---
name: anti-patterns
description: Common ways prior work on this task has gone wrong. Lead with these — most of them are not obvious from the data alone.
when-to-load: Before you settle on a fitting procedure or evaluation slice. Useful as a checklist after you have a working model and want to know what blind spots to look for.
load-cost: ~600 words.
---

# Anti-patterns to avoid

Lead with these. Most of them have surfaced repeatedly even on careful work. Read once, internalise, do not assume you'll spot the trap when you're in it.

*Anti-patterns are about avoiding known traps — they're not about avoiding ambition. Trying a Pacejka tyre model isn't an anti-pattern even if it doesn't work; fitting on Mach-E only and shipping for both platforms is.*

## Fit on one platform, ship for both

The two Ford platforms have very different dynamics: Lightning is ~30% heavier with a longer wheelbase, and its understeer signature is much stronger. If you fit `K_us`, effective wheelbase, or steering-scale on Mach-E only, the Lightning will be wildly over- or under-corrected — and vice versa. The pooled score absorbs this poorly. If you fit per-platform parameters, fit them per-platform. If you fit pooled parameters, evaluate on both before declaring success.

You should improve on this if you can.

## Splitting train/dev at the sample level inside a segment

Adjacent samples at 50 Hz are tightly correlated — the vehicle barely moves between samples. Splitting "every 5th sample to dev" leaks essentially all the information across the boundary; your dev RMSE will look great and tell you nothing about generalisation. The same problem applies to random segment splits where segments from the same route end up on both sides.

Hold out whole **routes**, not segments-from-anywhere. A `(device_id, route_id)` tuple identifies a route; segments under the same route should travel together to one side or the other.

You should improve on this if you can.

## Pinning to per-segment bias removal

Tempting: subtract the per-segment mean of `(yr_pred − yr_meas)` on straight rows, ship. This always helps in-sample yaw RMSE. But: (a) the bias is not constant within a segment, so a small time-varying residual survives and shows up as cross-track drift in CTE; (b) at inference time on new segments the bias must be re-computed from those segments, which is noisy on short or low-steering data; (c) it leaves the underlying physical bias unfixed. The trick is a floor, not a ceiling. Models that add an understeer term *on top of* (or instead of) the bias trick consistently beat bias-only on both KPIs.

You should improve on this if you can.

## Optimising one KPI while ignoring the other

A model that drops yaw RMSE by 40% but barely moves CTE has a *systematic yaw-rate bias* that integrates into trajectory drift. Conversely, a model that wins CTE but loses yaw RMSE is noisy but unbiased — fine for trajectory, bad for control. Always check both. If the yaw gap is much larger than the CTE gap, you have residual bias to chase. See `two-kpi-tradeoff.md`.

You should improve on this if you can.

## Trusting tool-supplied bounds and priors

Helpers may ship with `K_us` bounds, `C_alpha` bounds, default time constants, or initial guesses. If your fit pegs an upper or lower bound, that's not a finding — that's the bound being wrong for your platform. Widen and re-fit. The same applies to the openpilot `carParams` priors in `code/parameters.py`: they're calibrated for upstream use, not ground truth on this dataset. Fitted `g` and `L_eff` values typically don't match those priors; the data wins.

You should improve on this if you can.

## Time spent on Tesla

Tesla `sim.csv` files have no `yaw_rate_meas_rads` channel — no truth to fit against. Time spent fitting Tesla yields no improvement on the scored KPIs. Fall back to V0 passthrough for Tesla in `predict.py` and don't fit; the brief is permissive of this.

You should improve on this if you can.

## Per-segment fitted parameters that can't be inferred at inference time

If you fit `δ₀` per segment using truth data, you cannot apply that at inference time on a new segment — the truth isn't there. Anything you fit per segment must be derivable from that segment's *own data* (typically from straight-driving samples). If your model's parameters depend on truth, you have a calibration procedure, not a model.

You should improve on this if you can.
