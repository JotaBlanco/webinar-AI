---
name: approach-menu
description: A map of the option space for improving lateral fidelity. Mixes well-explored approaches with paths that haven't been tried on this data yet. Annotated so you can see which corners of the map are converged and which are open.
when-to-load: When choosing what to try next on top of V0, or when stuck after a first attempt.
load-cost: ~1000 words.
---

# Approach menu — a map of the option space

This is a map, not a ladder. Each option is annotated with one of:

- **[explored]** — multiple prior attempts have landed here; behaviour is well-characterised on this data.
- **[lightly tried]** — a few attempts; signal exists but not conclusive.
- **[unexplored]** — nobody has shipped this on this dataset yet. The annotation says nothing about whether it works — only that the data doesn't tell us yet.

The well-explored corner is "linear bicycle steady-state with understeer + small first-order yaw lag, fit per platform". It's a real local optimum, but the residual it leaves still amounts to ~0.005-0.01 rad/s yaw error and ~80-120 m of cross-track drift on the harder platform. That residual has structure. Several things that might capture it haven't been tried.

## Physics-based options — a ladder, not a flat list

**Two parallel strategies exist for improving on V0:**
- **Refine coefficients on your current rung** — fit better understeer, add per-segment δ₀, polynomial steering scale, longer τ. *Prior cohorts' winning recipes have lived here.* The dataset has rewarded this path.
- **Climb a rung — upgrade the model structure itself.** A more expressive structural model can capture residual sources the lower rung physically cannot. *No prior agent has shipped a working version above rung 0 on this dataset.* That is not evidence the higher rungs don't work — only that no one has tried hard enough yet. Both strategies are legitimate ambition.

The four rungs of structural complexity:

- **Rung 0 — Kinematic single-track with steady-state understeer** *[explored, V0 lives here]*. `yr_ss = v · δ / (L + K_us · v²)`. Typical `K_us ~ 0.001-0.005`, F-150 higher. Add steering scale `g` and offset `δ₀` for ~10-20% more. Big initial jump, then diminishing returns. Residual it leaves: per-segment offset (addressable on this rung with the δ₀ trick) and transient under-fit (NOT addressable on this rung — you've reached the rung's ceiling). *Cost to refine on this rung: minutes with `fit-model` (supply a 5-line `predict_factory` that builds rung-0 from `{g, delta0, K_us, L_eff, tau}`). Cost to climb: see rung 1.*

- **Rung 1 — Linear single-track dynamic with slip angles** *[unexplored on this data]*. Computes front/rear slip angles `α_f, α_r` from yaw rate and steering, lateral force `F = C_α · α`, integrates the yaw-rate equation of motion (no closed-form steady-state assumption). The closed-form `(1 + K_us·v²)` term is the *steady-state limit* of this model; the gain on this rung comes from the **transient response**, not from steady-state numbers. Residual it addresses: transient-regime under-fit (where rung 0's first-order lag is a band-aid). Needs `C_α_front` and `C_α_rear` per platform (the openpilot priors in `code/parameters.py` are known to be off — fit them from data). *Cost to climb: ~50-100 lines, 2 extra fitted params per platform. Worth it if your residual is transient-regime-dominated — check the regime breakdown from `scoring-model` first.*

- **Rung 2 — Nonlinear tyre (Pacejka, Fiala, brush)** *[unexplored on this data]*. Replaces rung 1's linear `F = C_α · α` with a saturating force curve. Residual it addresses: high-`a_lat` segments where the linear tyre overshoots (tyre operating beyond linear range). Most segments don't push tyres into saturation, so gain may be modest unless your residual is concentrated in those segments. *Cost to climb: 30-60 extra lines on top of rung 1, plus 2-3 more fitted params per platform. Risk: fitting Pacejka well needs more variation in `a_lat` than this dataset may provide.*

- **Rung 3 — Multi-body / weight-transfer** *[unexplored, probably overkill]*. Couples longitudinal and lateral; load transfer modifies effective `C_α` per axle dynamically. *Cost to climb: significant. Probably not worth it on this dataset because `v` is clamped (longitudinal dynamics partly removed) — but listed for completeness.*

**Deciding whether to climb vs refine.** The diagnostic is your residual's *shape*, not its *magnitude*. Use `scoring-model`'s per-regime split:
- Residual concentrated in `straight` regime → bias source; refine on your current rung (δ₀, K_us).
- Residual concentrated in `steady` regime → coefficient mismatch; refine on your current rung (g, polynomial g, K_us per platform).
- Residual concentrated in `transient` regime → **rung-0 first-order lag is a band-aid for an ODE you're not solving**. This is the canonical "climb the ladder" signal.
- Residual distributed roughly evenly → mixed; refine cheaply first, climb only if refinement plateaus far from V0.

You should improve on this if you can.

## Signal-processing and filter options

- **First-order yaw-rate lag** *[explored]*. `τ ≈ 50-80 ms`. Most gains in transient regime. Cheap; stacks on anything.

- **Higher-order steering dynamics** *[unexplored]*. Second-order filter with damping captures overshoot/undershoot the first-order can't. Adds 1-2 parameters; risk of overfit.

- **Complementary filter with `a_lat_meas_mps2`** *[unexplored, multiple agents suggested]*. `a_lat / v` is an alternative estimate of yaw rate. Fusing it with the bicycle-model output via a complementary filter or Kalman update may dampen sensor-specific noise and bias. The channel is sitting in the sim.csv unused.

- **State-space Kalman / EKF** *[unexplored]*. Treat yaw rate as a state with a process model (bicycle dynamics) and measurement update. Useful when the model is trustworthy in some regimes and the sensor in others. Heavy lift.

You should improve on this if you can.

## Data-driven and hybrid options

- **Residual learner on a physical prior** *[lightly tried]*. Fit physics first (KS + understeer + lag), regress the residual on features like `[v, |a_lat|, |δ|, sign(δ̇), v·δ]`. Small linear or ridge model. The residual is much smaller than the original signal, so a simple model works — overfits easily; bound feature count and validate.

- **Pure ML (linear, ridge, GP, MLP)** *[unexplored]*. Skip physics, fit a regression from raw inputs to truth yaw rate. Risk: overfitting platform-specific quirks; cross-platform generalisation unclear. Physics-prior path is usually safer.

- **Recurrent / sequence models (LSTM, GRU, 1D-CNN)** *[unexplored]*. Capture temporal dynamics. Theoretically attractive for transient regime; practically demanding (training time, framing, generalisation).

You should improve on this if you can.

## Structural extensions

- **Per-platform fits** *[explored, essential]*. Two Fords, two parameter sets. The pooled fit averages over them and wins less. Don't pool.

- **Polynomial steering scale** `g(δ) = g₀ + g₁·δ + g₂·δ²` *[explored, partial]*. Mach-E shows steering nonlinearity the linear `g` can't capture. **The catch**: polynomial g closes *yaw* residual but rarely closes *CTE* alone — three prior agents shipped polynomial g and got nothing on Mach-E CTE. **Combine with per-segment δ₀** (see `anti-patterns.md` § "Legal cousin") to convert the yaw win into a CTE win. Fit-stability warning: `g₀` and `L_eff` trade off (scale-invariant in the linear regime), so the optimiser degenerates if you fit both unconstrained — constrain `L_eff` to wheelbase ± 20% (Mach-E ~2.85m, Lightning ~3.7m) or hold `L_eff` fixed at the carParams value.

- **Speed-dependent understeer** `K_us(v) = K₀ + K₁·v + …` *[unexplored]*. The standard `K_us·v²` term assumes constant `K_us`. If understeer varies with speed (or `a_lat`), a richer parameterisation may help. Small effect; unexplored.

- **Per-regime models** *[unexplored]*. Different model in straight vs cornering vs transient. Cost: more params, regime-boundary discontinuities. Most useful if you suspect one regime dominates the residual.

- **`a_lat_meas_mps2` as a model input** *[explored, two distinct uses]*. (a) **As a straight-line *detector*** — rows with `|a_lat_meas| < 0.3 and v > 5` identify when the vehicle is not turning, which is the gating rule for the per-segment δ₀ recipe in `anti-patterns.md`. This is the highest-leverage use of `a_lat_meas` on this dataset. (b) **As an alternative yaw-rate estimate** for sensor fusion (`yr_alt = a_lat / v`) — promising on paper, no agent has shipped a working version that beats per-segment δ₀.

You should improve on this if you can.

## Things that have not produced gains

- **Per-segment bias removal using truth at inference** *[illegal]*. Truth isn't there at scoring time — submission fails. See `anti-patterns.md`. (Note: the *legal* input-derived per-segment δ₀ in the same doc IS a winning move when platform-gated.)
- **Aggressive trajectory smoothing** *[explored, wrong axis]*. Lowers noise without addressing the bias source that drives CTE.
- **Tesla coefficients by analogy** *[explored, useless]*. No truth channel; V0 passthrough is the honest fallback.

You should improve on this if you can.

## Worked example — polynomial g combined with per-segment δ₀

The combo that converts a yaw-only win into a CTE win on Mach-E:

```python
def _g_eff(delta_in, g0, g2):
    """Quadratic-in-|δ| steering scale. Symmetric in sign."""
    return g0 + g2 * delta_in * delta_in

def predict_mache(sim_df, p):
    # 1. Per-segment δ₀ from input channels (see anti-patterns.md "Legal cousin")
    delta0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
    delta_in = sim_df["delta_road_rad"].to_numpy() - delta0
    # 2. Polynomial g — quadratic only (linear term traded off against L_eff)
    g_eff = _g_eff(delta_in, p["g0"], p["g2"])
    delta = delta_in * g_eff
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    # ... first-order lag as before
```

Why this works and the linear-g alone doesn't: polynomial g closes the steering-nonlinearity gap that produces high-curvature yaw error; per-segment δ₀ closes the segment-by-segment offset that integrates into trajectory drift. Each addresses a different residual source. Shipping just polynomial g leaves the offset uncorrected — CTE barely moves.

## Platform-gating heuristic — before applying any per-segment trick

Before turning on a per-segment correction (δ₀, K_us-tweak, anything that varies between segments) for a platform, **run this diagnostic on your dev set**:

```
for each segment:
    seg_bias = median(yr_pred - yr_meas_truth)   # signed
collect bias values across segments per platform
report std(seg_bias) per platform
```

- If `std > ~0.002 rad/s` on a platform, per-segment correction is worth it for that platform (Mach-E currently qualifies — std ~0.005–0.007).
- If `std < 0.002 rad/s`, the per-segment correction adds noise without adding signal (Lightning currently fails this test — std ~0.001).

Gate by platform. The same trick can help one and hurt the other on the same dataset.

## On choosing

Look at your own residual first. If the bulk of your error is in the transient regime, dynamic ST or a higher-order steering filter is plausible. If it's in steady cornering, the closed-form understeer is already close to optimal — gains will come from per-platform refinement, polynomial steering combined with per-segment δ₀, or constrained joint fits. If it's noise-dominated, a Kalman filter or robust loss may help. The annotations above tell you which paths are worn smooth and which still have ground to cover.

---

## Failure-mode index — check before you commit

| You'll see this if... | What it points to |
|---|---|
| you tried polynomial g and only yaw improved, not CTE | combine polynomial g with per-segment δ₀ to convert yaw into CTE |
| your joint fit of `g` and `L_eff` keeps degenerating | g × L is scale-invariant — constrain one (see polynomial-g section) |
| you applied the same per-segment correction to both platforms and one got worse | platform-gate it — see the diagnostic above |
| you spent most of your budget on Tesla | Tesla has no truth — V0 passthrough is the honest fallback |
| you tried a Kalman / EKF and your code complexity exploded with no CTE gain | the heavy lift wasn't justified by this dataset's residual structure — fall back to simpler |
| you skipped the residual-shape check and went straight to a tyre model | look at your residual first — dynamic / nonlinear tyre is unjustified unless the transient regime dominates |
