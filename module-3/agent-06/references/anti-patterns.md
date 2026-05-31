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

## The legal cousin — per-segment δ₀ from input channels (this is a winning move on the right platform)

The valuable per-segment trick **estimates δ₀ from input channels only**, never from truth. Recipe that has worked on this data:

1. From the segment's own data, find rows where the vehicle is driving straight: `|a_lat_meas_mps2| < 0.3` and `v_mps > 5`. These are rows where any nonzero `delta_road_rad` is *steering offset*, not steering input.
2. If you have ≥ 50–100 qualifying rows, set `δ₀_segment = median(delta_road_rad)` over those rows. Otherwise fall back to a platform-wide δ₀.
3. Subtract `δ₀_segment` from `delta_road_rad` before computing yaw rate.

This uses only input channels. Legal at inference time. **But: gate it by platform.** On this dataset:

- **Mach-E**: per-segment yaw-bias scatter is wide (std > 0.002 rad/s); per-segment δ₀ closes most of the CTE gap.
- **Lightning**: steering offset is stable across segments; applying per-segment δ₀ *hurts* — use a single global δ₀ here.

The diagnostic test before turning per-segment δ₀ on for a platform: compute `median(yr_pred - yr_meas_truth_dev)` per segment on your *dev set*, take the std across segments. If > 0.002 rad/s, per-segment correction is worth it. If not, don't bother.

### Worked example — recipe drawn from a prior top-performing predict()

```python
import numpy as np
import pandas as pd

def _per_segment_delta0(sim_df, fallback=0.0,
                        ax_thresh=0.3, v_thresh=5.0, min_rows=50):
    """Estimate δ₀ from THIS segment's own straight-driving rows.
    Uses input channels only — legal at inference time."""
    mask = (sim_df["a_lat_meas_mps2"].abs() < ax_thresh) & (sim_df["v_mps"] > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())

PLATFORM_PARAMS = {
    "FORD_F_150_LIGHTNING_MK1": {
        "use_per_segment_delta0": False,        # platform-gated OFF (tight bias spread)
        "delta0": 0.00133,
        "g": 0.863, "L_eff": 3.26, "K_us": 0.00350, "tau": 0.060,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "use_per_segment_delta0": True,         # platform-gated ON (wide bias spread)
        "delta0_fallback": -0.0001,
        "g": 0.891, "L_eff": 2.22, "K_us": 0.00202, "tau": 0.069,
    },
}

def predict(sim_df, platform):
    if platform not in PLATFORM_PARAMS:
        return sim_df[["yaw_rate_pred_rads"]].copy()  # Tesla — V0 passthrough
    p = PLATFORM_PARAMS[platform]
    delta0 = (_per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
              if p["use_per_segment_delta0"] else p["delta0"])
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    # First-order lag, discretised over the segment's own dt.
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
```

Recipe drawn from `m3-agent-09`'s shipped model (CTE +51.8% over V0 on the canonical eval). Note three things: (1) `delta0` comes from input channels only; (2) it's *platform-gated* (Lightning uses a global δ₀, Mach-E uses per-segment); (3) Tesla passes through V0 because it has no truth channel to fit against. The `PLATFORM_PARAMS` numbers above are an existing fit — to find your own, wrap this shape in a `predict_factory(platform, coeffs)` and call `fit-model` with `objective="cte"` (the bias-spread check determines which platforms get `use_per_segment_delta0=True`).

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

---

## Failure-mode index — check before you commit

Quick pre-commit checklist. If any of these describe what you're about to do, stop and revisit the relevant section above.

| You'll see this if... | The trap it points to |
|---|---|
| your predict reads `yaw_rate_meas_rads` from the input frame | illegal per-segment bias removal (truth peek) — submission fails at grading |
| your dev RMSE is wildly better than your train RMSE on one platform | per-segment fit overshooting on a platform that doesn't need it (probably Lightning) |
| you're holding out individual segments instead of whole routes for dev | sample-level / random-segment leakage |
| you've tuned all your coefficients on Mach-E and your Lightning numbers got worse | fit on one platform, shipped for both |
| your fitted `K_us` is pegged at a bound | bound is wrong for your platform — widen and re-fit |
| your `predict` raises on Tesla because it depends on truth | Tesla has no truth — V0 passthrough is the honest fallback |
| your yaw RMSE drops 40% but CTE barely moves | residual is per-segment bias — see "Legal cousin" section + `two-kpi-tradeoff.md` |
| your fit reports `g₀ × L_eff` keep diverging in opposite directions | g ↔ L_eff scale-invariance; constrain one or both (see `approach-menu.md`) |
