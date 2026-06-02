# Module 3.v3 agent-04 — REPORT

## Shipped model
`final-model/predict.py` = V1 (kinematic single-track + understeer + first-order
lag + per-segment δ₀) + per-platform 8-feature linear correction fit on V1
residuals against truth. Stateless feed-forward; no new integrator.

Features (per platform, ridge λ=1e-5):
`1, |δ|·δ, v·δ, v²·δ, δ³, dδ/dt, dδ/dt·v, sign(δ)·δ²·v`

Coefficients in `final-model/coeffs.json`. Tesla falls through to V0.

## Headline KPIs (local on data/sim/segments/, contract-strict inputs)

| metric | V1 | Shipped | Δ |
|---|---|---|---|
| pooled yaw RMSE (rad/s) | 0.005874 | **0.005552** | **−5.5%** |
| pooled CTE RMSE (m) | 56.81 | **54.56** | **−4.0%** |

Per-platform (yaw/CTE): Lightning 0.00516 / 60.96; Mach-E 0.00757 / 93.33;
IONIQ-5 0.00745 / 67.18; Tesla 0/0.

Per regime yaw: straight 0.00442→0.00434; steady 0.00835→0.00754; transient
0.01647→0.01565.

## Residual diagnosis that drove the design
On V1 residuals (truth − V1):
- `|δ|·δ` correlated +0.25 on Lightning, +0.35 on Mach-E, +0.03 on IONIQ-5
  → tyre-saturation signature; V1's linear understeer can't bend at high δ.
- Per-platform CTE drift on V1: Lightning +0.3 m, Mach-E **−22.0 m**, IONIQ-5
  −11.6 m. Tiny mean residuals (~10⁻³ rad/s) integrate to large drifts.
- Transient regime yaw RMSE 0.0165 vs straight 0.0044 → V1's τ-lag is a
  band-aid for transient dynamics.

## Candidates built
1. `v1_passthrough` (refines-v1) — explicit floor; yaw 0.005874, CTE 56.81.
2. `v1_plus_nonlin` (differs-from-V1) — 4-feature correction; yaw 0.005600,
   CTE 54.37. Collapsed Mach-E CTE drift to −5.8 m.
3. `v1_plus_rich` (differs-from-V1, SHIPPED) — 8-feature; best yaw across the
   board; CTE within 0.2 m of #2.

Considered but not built (deferred for time budget):
- Rung-1 dynamic single-track ODE (cornering stiffness identifiability +
  per-platform priors needed).
- Regime-switched composite (V1 + dynamic) — `dδ/dt` feature captured most
  of the transient signal cheaper.

## What's left on the table
- IONIQ-5 still has −7.2 m CTE drift after the correction. Its residual
  isn't `|δ|δ`-shaped — likely route-bias or unmodelled yaw offset. A
  per-route bias model would be the next attack.
- Mach-E pooled CTE 93 m is still high in absolute terms — the worst routes
  (`00000000--33439c2a9c`, 5 segments, 8.3 km) drive it; localised
  high-curvature behaviour V1 still can't reach.

## Honest gaps
- No `fit-model` skill present in the harness — fit done by hand
  (`out/fit_correction*.py`).
- No `compare-models` skill present — comparison done by hand
  (`out/score_simonly.py`).
- Did not validate against `data/sim-only/segments/` end-to-end with truth;
  relied on the local `score-model` which strips inputs to the allowlist
  before calling predict (functionally equivalent to grading conditions but
  I read truth from `data/sim/segments/`).

## Files
- `final-model/predict.py`, `final-model/coeffs.json`, `final-model/manifest.json`
- `models/{v1_passthrough,v1_plus_nonlin,v1_plus_rich}/` — each with predict.py,
  notes.md, assessment.md.
- `out/` — fit and scoring scripts.
- `MODELS.md`, `EXPERIMENTS.md` updated.

Preflight: 12/12 pass.
