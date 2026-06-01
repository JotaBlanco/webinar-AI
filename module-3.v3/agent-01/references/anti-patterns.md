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

## Per-segment bias removal — the illegal version (don't do this)

Tempting: at inference time, compute the per-segment mean of `(yr_pred − yr_meas_truth)` on straight rows, subtract, ship. This always helps in-sample yaw RMSE. But the truth channel (`yaw_rate_meas_rads`) **doesn't exist** in the operating-contract input (`sim-only/`). The canonical grader will hand your `predict()` a sim_df with no truth column; this approach raises `KeyError` and your submission fails. **Even if it didn't, this is calibrating to the answer — useless on any unseen data.**

You should improve on this if you can.

## The "legal cousin" — per-segment δ₀ from input channels

The *illegal* per-segment bias removal above has a legal cousin: estimate a per-segment steering offset `δ₀` from the segment's *own straight-driving rows*, using only allowlist channels (e.g. a straight-row gate on `|yaw_rate_pred_rads|` or `|delta_road_rad|`, then `δ₀ = median(delta_road_rad)` over those rows). No truth involved, legal at inference time.

This is already part of `code/v1_baseline.py` (the pre-shipped rung-0 ceiling). It is **not** the headline move for m3.v3 — V1 has it built in and the m3.v2 cohort showed it caps out around the V1 numbers regardless of whose hands fit the coefficients. Mention here so you don't re-derive it from scratch thinking it's new.

The thing worth knowing for *new* model shapes:
- Anything you estimate per-segment must be derivable from that segment's own allowlist data. δ₀ from a straight-row gate qualifies; a per-segment scale factor fit against truth doesn't.
- `a_lat_meas_mps2` is denied at grading time (kinematic shadow of truth). If a recipe you find online uses it as a straight-row gate, substitute an allowlist proxy: `|v_mps * yaw_rate_pred_rads|`, `|yaw_rate_pred_rads|`, or `|delta_road_rad|`.

If you only do δ₀ refinement, your score will equal V1 — that is the point of pre-shipping V1.

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

---

## Failure-mode index — check before you commit

Quick pre-commit checklist. If any of these describe what you're about to do, stop and revisit the relevant section above.

| You'll see this if... | The trap it points to |
|---|---|
| your predict reads `yaw_rate_meas_rads` from the input frame | illegal per-segment bias removal (truth peek) — submission fails at grading |
| your predict reads `a_lat_meas_mps2` from the input frame | denied column (kinematic shadow of truth) — works locally against `data/sim/`, fails at preflight and grading. Use the legal-cousin gates above. |
| your dev RMSE is wildly better than your train RMSE on one platform | per-segment fit overshooting on a platform that doesn't need it (probably Lightning) |
| you're holding out individual segments instead of whole routes for dev | sample-level / random-segment leakage |
| you've tuned all your coefficients on Mach-E and your Lightning numbers got worse | fit on one platform, shipped for both |
| your fitted `K_us` is pegged at a bound | bound is wrong for your platform — widen and re-fit |
| your `predict` raises on Tesla because it depends on truth | Tesla has no truth — V0 passthrough is the honest fallback |
| your yaw RMSE drops 40% but CTE barely moves | residual is per-segment bias — see "Legal cousin" section + `two-kpi-tradeoff.md` |
| your fit reports `g × L_eff` keep diverging in opposite directions | g ↔ L_eff scale-invariance; constrain one or both, or pin to a physical wheelbase from `code/parameters.py` |
| you matched V1 to 3 decimals | V1 is the floor — you tuned coefficients but didn't change the model |
