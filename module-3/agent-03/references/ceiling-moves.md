---
name: ceiling-moves
description: Four candidate moves above the current best-known ceiling on this dataset. Each was named by top prior agents as "I would have tried this with more time" but none has been shipped in a working form. Load this when you have already exhausted the standard moves (`approach-menu.md`) and want to push past the ~+38% yaw / +52% CTE ceiling the top three prior runs clustered at.
when-to-load: After you've shipped a model that already beats V0 by ≥+30% on both KPIs. Loading earlier wastes the doc — these moves only pay off on top of a solid base.
load-cost: ~700 words.
---

# Ceiling moves — the next leap

The current cluster of best-known results sits at Mach-E CTE ~70 m, Lightning CTE ~62 m, pooled yaw RMSE ~0.0089 rad/s. All three top prior runs landed within ~3 m of each other on Mach-E CTE — they're at a ceiling. The unexplored compound move below is what top performers named but didn't get to. None is *known* to work; each is plausible enough to be worth one focused attempt.

## 1. Multi-seed / fold-averaged fitting *[highest ROI for the code-cost]*

Symptom that says you need this: your dev-set KPIs swing by ≥10% as you change the seed of your train/dev split, even though your final per-platform fits look stable.

What it is: call `fit-model` on **K different route-level train/dev splits** (K=3 to 5 is enough), average the resulting parameter vectors. Ship the averaged model.

Why it helps: parameter fits on a single split are noisier than the underlying residual structure. Different splits land on slightly different local optima; the average is smoother and *typically* generalises better. One prior agent found that seed=0 gave dev CTE 134 while seeds 1–4 gave ~70 — averaging would have collapsed that noise.

Cost: ~20 lines wrapping a loop around `fit-model`. No new physics, no extra fitting infrastructure.

Failure mode: if your residual is bias-dominated and the bias is identical across all routes, averaging adds nothing. Cheap to test — try it and see.

## 2. CTE-aware fit *[now a one-line config change]*

Symptom: your yaw RMSE is excellent on dev but CTE only gets a fraction of that improvement. You fitted your coefficients against yaw-RMSE only.

What it is: pass `objective="cte"` (or `objective="yaw_plus_cte"` with `cte_weight`) to `fit-model`. The skill integrates each segment's trajectory under the candidate coefficients and minimises CTE RMSE directly. Yaw-MSE alone is indifferent to the *sign* and *temporal coherence* of residuals; a CTE-aware fit penalises the coherent biases that drive trajectory drift.

Previously this was a heavy 50-100 line undertaking — two prior cohort agents prototyped it but neither finished within budget. With `fit-model` it's a one-line objective change against the same parametrised model. Run it again with `objective="cte"` and compare to your yaw-fitted variant.

Cost: each fit is ~3-5× slower than yaw-fitting (trajectory integration per loss eval), but no new code. Subsample your train segments if budget is tight.

Failure mode: if your residual is already bias-corrected (per-segment δ₀ is on), the CTE-aware fit has nothing left to bite on — it converges to similar coefficients as the yaw fit.

## 3. Constrained joint fit of polynomial g and L_eff *[also a one-line change with fit-model]*

Symptom: you tried polynomial g and the optimiser produced bizarre values (`g₀ = 0.3`, `L_eff = 6.5` — clearly off). One prior agent abandoned polynomial g on Lightning for exactly this reason.

What it is: `g` and `L_eff` are mathematically degenerate at low δ (you can scale them in opposite directions and get the same steady-state yaw rate). Pass `bounds={"L_eff": (L_nominal*0.8, L_nominal*1.2)}` to `fit-model` (auto-routes to L-BFGS-B), or hold `L_eff` fixed at the `carParams` value and only fit `g`.

Why it helps: removes the degeneracy that turns the optimiser into a random walk.

Cost: one bounds dict in your `fit-model` call.

Failure mode: if your nominal `L_eff` is far from optimal for one platform, fixing it caps the polynomial-g gain.

## 4. Climb a structural rung — dynamic single-track with slip angles *[start here if your residual is transient-dominated]*

Symptom: after per-segment δ₀ and polynomial g, your residual concentrates in the *transient regime* (segments with high `|d(delta)/dt|`). The rung-0 first-order yaw lag is a band-aid for an ODE you're not solving.

What it is: climb from rung 0 to rung 1 of the model-structure ladder (see `approach-menu.md` § "Physics-based options — a ladder"). Replace the steady-state `yr_ss = v · δ / (L + K_us · v²)` with the actual lateral-dynamics ODE — compute front/rear slip angles `α_f, α_r` from yaw rate and steering, compute lateral force `F = C_α · α`, integrate the yaw-rate equation of motion forward. Needs `C_α_front`, `C_α_rear` per platform (the openpilot priors in `carParams` are known to be off — fit from data using `fit-model`, supplying a `predict_factory` that builds the rung-1 dynamics from `{C_alpha_f, C_alpha_r, L_eff, m, Iz}`).

Why it helps: the steady-state model assumes instantaneous response to steering input. Real vehicles have transient dynamics governed by slip-angle build-up. In transient-heavy segments this is what the first-order lag is band-aiding — climbing the rung addresses it physically.

Cost: 50–100 lines for the dynamics + integrator factory function. `fit-model` handles the parameter optimisation. Two extra fitted params per platform. Risk of overfit if you can't validate carefully.

When to start here vs at moves 1–3: **if your `scoring-model` regime breakdown shows the transient regime dominates the residual, this is move 1 for you, not move 4**. Moves 1-3 are coefficient refinements on rung 0; if you're already at rung 0's ceiling on transient segments, no coefficient refinement will help. Climb instead.

Failure mode: if your residual is NOT concentrated in the transient regime, climbing the rung buys very little. Several prior agents named dynamic ST as the natural next move without first checking whether the data supported it. The regime breakdown is the diagnostic that decides.

## Sequencing if you're going to try more than one

The right starting move depends on your residual's *shape*, not its magnitude. Check the per-regime breakdown from `scoring-model` first:

- **Residual mostly in straight / steady regimes** → moves 1-3 in order. Move 1 (fold averaging) first as cheap insurance, then 3 (constrained joint fit), then 2 (CTE-aware loss).
- **Residual concentrated in transient regime** → **move 4 first**, then 1-3 on top of the new structural model. Don't grind out moves 1-3 on a rung-0 model that can't capture the residual shape — climb first.
- **Mixed residual** → moves 1 + 3 first (cheap), then check the regime breakdown again. If transient is now the dominant share, climb to rung 1.

You should improve on this if you can.
