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

## Physics-based options

- **Kinematic single-track with steady-state understeer** *[explored]*. `yr_ss = v · δ / (L + K_us · v²)`. Typical `K_us ~ 0.001-0.005`, F-150 higher. Add steering scale `g` and offset `δ₀` for ~10-20% more. Big initial jump, then diminishing returns.

- **Linear single-track (dynamic, with slip angles)** *[unexplored on this data]*. Computes front/rear slip angles `α_f, α_r` from yaw rate and steering, lateral force `F = C_α · α`, yaw-rate equation of motion (no closed-form steady-state assumption). The closed-form `(1+K_us·v²)` term is the *steady-state limit* of this model; gain comes from the transient response, not from steady-state numbers. Needs `C_α` per platform — the openpilot priors are known to be off, fit from data.

- **Nonlinear tyre model (Pacejka, Fiala, brush)** *[unexplored on this data]*. Saturating lateral force at high slip. May help in high-curvature, high-`a_lat` segments where the linear tyre overshoots. Most segments don't push tyres into saturation, so gain may be modest — but the transient regime carries the largest remaining residual.

- **Multi-body / weight-transfer extensions** *[unexplored, probably overkill]*. Couples longitudinal and lateral. Probably not worth it given `v` is clamped.

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

- **Polynomial steering scale** `g(δ) = g₀ + g₁·δ + g₂·δ²` *[unexplored]*. Mach-E shows steering nonlinearity the linear `g` can't capture — its CTE gap is the hardest to close. Polynomial may absorb the curvature. Risk: overfit.

- **Speed-dependent understeer** `K_us(v) = K₀ + K₁·v + …` *[unexplored]*. The standard `K_us·v²` term assumes constant `K_us`. If understeer varies with speed (or `a_lat`), a richer parameterisation may help. Small effect; unexplored.

- **Per-regime models** *[unexplored]*. Different model in straight vs cornering vs transient. Cost: more params, regime-boundary discontinuities. Most useful if you suspect one regime dominates the residual.

- **`a_lat_meas_mps2` as a model input** *[unexplored, multiple agents wished they'd tried]*. The measured lateral accel is informative about what the tyres are actually doing. Adding it as a feature or constraint may close gaps the steering signal alone can't.

You should improve on this if you can.

## Things that have not produced gains

- **Per-segment bias trick alone** *[explored, insufficient]*. Looks like a win on yaw RMSE, loses on CTE. See `anti-patterns.md`. Stack other corrections on top if you use it.
- **Aggressive trajectory smoothing** *[explored, wrong axis]*. Lowers noise without addressing the bias source that drives CTE.
- **Tesla coefficients by analogy** *[explored, useless]*. No truth channel; V0 passthrough is the honest fallback.

You should improve on this if you can.

## On choosing

Look at your own residual first. If the bulk of your error is in the transient regime, dynamic ST or a higher-order steering filter is plausible. If it's in steady cornering, the closed-form understeer is already close to optimal — gains will come from per-platform refinement, polynomial steering, or `a_lat` fusion. If it's noise-dominated, a Kalman filter or robust loss may help. The annotations above tell you which paths are worn smooth and which still have ground to cover.
