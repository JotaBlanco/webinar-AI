---
name: build-your-own-model
description: When the 8 physics-catalog models don't fit the residual you're seeing, build a 9th. This doc names the four orthogonal dimensions of structural diversity that produced the existing catalog, gives 8 concrete sketches for new models the cohort hasn't tried, and walks through the 7-step recipe for shipping one into the catalog so the next cohort inherits it.
when-to-load: After at least one catalog model has been iterated past its first fit AND the residual is still showing structure that the existing models don't capture. Not first thing — start by picking from the catalog.
load-cost: ~900 words.
updated: 2026-06-02
---

# build-your-own-model — extending physics-catalog

The 8 catalog models are not the search space; they're seed points in it.
This doc names the dimensions you can move along, sketches 8 candidate
extensions, and gives the recipe for shipping a new one back into the
catalog so the next cohort inherits it.

## The four dimensions of structural diversity

Every catalog model is a point in this 4-dimensional space. Two models
are "structurally different" iff they differ in at least one dimension.
This is the criterion the iterate gate's `## What this differs from`
section is asking about.

### 1. State vector

What state does the ODE carry between time steps?

- **0-state** (memoryless): V1, kinematic single-track. Each sample's
  yaw is a closed-form function of (δ, v) — no integration.
- **2-state [β, ψ̇]**: dst_lin, dst_nl, dst_regime, dst_load, dst_twin_track,
  dst_combined_slip, dst_steer_compliance. The canonical dynamic single-track.
- **4-state [β, ψ̇, F_yf, F_yr]**: dst_relax. Per-axle tyre force becomes
  a state because of carcass dynamics.

Other states you could add: roll rate φ̇, suspension travel, tyre temperature,
brake pressure dynamics, steering rate dynamics.

### 2. Tyre force model

How does F_y depend on α (slip angle) and F_z (normal load)?

- **None** (V1): no slip angle at all, geometric δ → ψ̇.
- **Linear** (dst_lin, dst_regime, dst_relax, dst_steer_compliance,
  dst_twin_track): F_y = -C_α · α.
- **Pacejka-lite saturating** (dst_nl): F_y = -μ·F_z·sin(C·atan(B·α)).
- **F_z-scaled linear** (dst_load, dst_twin_track): F_y = -C_α(F_z) · α.
- **Friction-circle limited** (dst_combined_slip): F_y = clamp(-C_α·α, ±F_y_max),
  F_y_max² + F_x² ≤ (μ·F_z)².

Other tyre models: brush model, MF6.2 full Pacejka, separately-fitted
front/rear shape factors, temperature-dependent C_α.

### 3. Geometric / mechanical coupling

What couplings between long, lat, vertical, and roll are modelled?

- **None** (dst_lin, dst_nl, dst_relax): pure lateral.
- **Long → vertical → lateral** (dst_load): a_long shifts F_z which
  rescales C_α.
- **Long ⊥ lateral via friction circle** (dst_combined_slip): F_x and
  F_y both consume the same friction budget.
- **Lateral → vertical → lateral** (dst_twin_track): a_lat shifts F_z
  per-wheel which rescales per-wheel C_α.
- **Steering → lateral → steering** (dst_steer_compliance): commanded δ
  reduced by F_yf via column compliance.

Other couplings: aerodynamic downforce (high speed → F_z increases →
yaw stiffness changes), road camber, banked turns.

### 4. Regime / gating

When is the model active, and what falls back when it isn't?

- **Unconditional** (dst_lin, dst_nl, dst_relax, dst_load, dst_twin_track,
  dst_combined_slip, dst_steer_compliance): always integrated.
- **Speed-gated smooth blend** (dst_regime): kinematic below θ, dynamic above.
- **Conditional on a_long** (dst_combined_slip — implicit, friction
  circle only bites under braking/acceleration).

Other gates: |α|-gated (use rung-1 only when tyre is in linear regime;
use rung-2 above), banked-vs-flat-gated, transient-vs-steady-gated.

---

## 8 model sketches the catalog doesn't ship — try one

Each is a one-paragraph design that fits the operating contract. Picked
because they're orthogonal to all 8 catalog models on at least one of the
four dimensions above. Listed roughly by ratio of (expected leverage) /
(implementation effort).

### 1. `dst_roll` — roll-rate state for camber-induced yaw

Add a third state φ̇ (roll rate) to dst_lin. Roll is driven by lateral
load: m·a_lat·h_cg − (k_φ·φ + d_φ·φ̇). Roll angle then induces a camber
thrust at the tyres (~ Cγ · φ) that adds to F_y. Closes the m4.v1
Lightning gap differently than dst_load: load transfer is steady-state,
camber thrust has phase lag. Fitted: {C_α*, I_z, h_cg, k_φ (roll
stiffness), d_φ (damping), Cγ (camber stiffness)}.

### 2. `dst_aero` — speed-dependent downforce / drag-induced load

At high v, aerodynamic downforce L = 0.5·ρ·v²·Cl·A_ref adds to F_z and
modifies effective C_α. Symmetric with dst_load but conditioned on v²
instead of a_long. Particularly relevant for highway-speed segments.
Fitted: {C_α*, I_z, Cl·A_ref}. One global parameter; cheap.

### 3. `dst_pacejka_full` — separately-fitted front/rear shape factors

dst_nl uses a single (μ, C) for both axles. Real Pacejka has separate
B/C/D per axle. 6 extra params (B_f, C_f, D_f, B_r, C_r, D_r — D is
the peak which differs front/rear). Likely overparameterised on this
data, but worth a one-shot to see whether front/rear saturation
asymmetry exists.

### 4. `dst_brush` — brush tyre model (no Pacejka)

Alternative to Pacejka — the brush model F_y(α, F_z) derived from first
principles assuming the tyre contact patch is a row of compliant brush
elements. Three fitted params per platform: tyre length L_p, brush
stiffness c_p, and μ. Often fits passenger-tyre data better than Pacejka.
Same operating-contract surface as dst_nl.

### 5. `dst_steer_rate` — steering-rate input dependence

V1's lag-τ correlates with d(δ)/dt (cohort §3). Most catalog models
ignore d(δ)/dt entirely. dst_steer_rate adds a tyre input lag of the form
δ_effective_τ ← δ_command - τ · d(δ)/dt. Different from dst_relax (which
lags the *force*); this lags the *input*. Cheap (1 param per platform),
fast to test as a sanity check that the steering-rate signature was real.

### 6. `dst_implicit_euler` — alternative integrator

Replace RK4 with implicit (backward) Euler. Same physics, different
integration. Particularly useful when dst_lin's eigenvalues are stiff
(small inertia / high stiffness regimes — Iz / m at minimum bounds).
The implicit step is more expensive per call but stable at larger dt;
might allow upsampling-free fits on sparse-time-step segments. Operating
contract unchanged.

### 7. `dst_v1_plus_gb_residual` — physics + learned residual head

Run dst_lin (or dst_nl, dst_relax — pick one) to produce a yaw
prediction, then add a small gradient-boosted regression head on the
*physics model's* residual using V1's allowlist features. Combines
cohort §4 (residual learner reliably +1-5%) with rung-1+ physics. The
data-driven head captures whatever the physics model misses; the
physics model carries the inductive bias the residual learner can't.
Fit pipeline: 1) fit dst_*; 2) compute residuals on dev; 3) GB-fit the
residual; 4) write both into a single coeffs.json.

### 8. `dst_per_platform_ridge_intercept` — per-platform additive bias on dst_lin

Add a per-platform constant offset to dst_lin's output (`yaw_rate_pred_rads
+= delta_bias_platform`). Tiny structural change, but cohort §2 says
per-platform bias is the most-shipped move. Combined with the inherent
rung-1 lift, this might be additive. **MUST run route-grouped CV**
(bias_without_route_cv gate refuses to ship otherwise) — fit.py should
write route_cv_sigma_yaw to coeffs.json.

---

## How to ship one back to the catalog

Pull request flow that lets the next cohort inherit your work:

1. **Sketch the model in one paragraph** on top of an existing model's
   `notes.md`. Name which of the 4 dimensions it changes.

2. **Copy a near-neighbour catalog model.**
   ```bash
   cp -r physics-catalog/dst_lin physics-catalog/dst_<your_name>
   ```
   Pick the catalog model with the closest state vector + tyre force.

3. **Edit `predict.py`.** Keep the function signature
   `predict(sim_df, platform) -> DataFrame`. Use helpers from
   `physics-catalog/_common.py` — `step_rk4_*`, `integrate_dst`,
   `get_platform_params`, `load_coeffs`.

4. **Edit `fit.py`.** Update the `FitSpec` (init, bounds, names) for
   your new params. Reuse `fit_with_route_cv` from `_common.py` — it
   handles route grouping + σ writing.

5. **Edit `coeffs.default.json`** with textbook priors for each platform.
   No bias terms unless you understand the bias_without_route_cv gate.

6. **Edit `notes.md`** — must include rung, parent, expected_residual,
   and a `## What this differs from` section. The iterate novelty gate
   refuses without it.

7. **Write `smoke.py`** — synthetic data, all 4 platforms, asserts
   finite output. Copy a near-neighbour model's smoke as a template.

8. **Add to the audit.** Update `physics-catalog/_audit.py`'s
   `CATALOG_MODELS` tuple. Run `python -m physics-catalog._audit`. Must
   be 100% green.

9. **Cross-reference.** Add a row to `physics-catalog/README.md`'s
   table and `references/physics-menu.md`'s residual-character mapping.

10. **(Optional) Wire into launch-rungs.** Edit
    `launch-rungs/manifest.yaml` if your model should be one of the
    6 default subagent slots. (Removing a slot to make room is fine —
    the slot for `rung-2-tyre-relaxation` or similar can be retargeted.)

The cohort ratchet is the same shape as
`references/m4-cohort-findings.md` — every cohort iteration grows the
catalog with what was tried and what worked.
