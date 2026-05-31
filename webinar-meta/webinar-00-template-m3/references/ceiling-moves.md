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

What it is: fit your model on **K different route-level train/dev splits** (K=3 to 5 is enough), average the resulting parameter vectors. Ship the averaged model.

Why it helps: parameter fits on a single split are noisier than the underlying residual structure. Different splits land on slightly different local optima; the average is smoother and *typically* generalises better. One prior agent found that seed=0 gave dev CTE 134 while seeds 1–4 gave ~70 — averaging would have collapsed that noise.

Cost: ~20 extra lines around your existing fit loop. No new physics.

Failure mode: if your residual is bias-dominated and the bias is identical across all routes, averaging adds nothing. Cheap to test — try it and see.

## 2. CTE-aware loss *[high ROI if you can afford the runtime]*

Symptom: your yaw RMSE is excellent on dev but CTE only gets a fraction of that improvement. Your loss function is yaw-MSE only.

What it is: add a heading-drift regulariser to the loss. Integrate predicted yaw rate over the segment to get a heading trajectory; penalise its drift from the truth heading trajectory. `loss = yaw_mse + λ · heading_drift_rmse`. Tune `λ` so heading-drift contributes ~20–40% of the total loss at the optimum.

Why it helps: yaw-MSE alone is indifferent to the *sign* and *temporal coherence* of residuals. A loss that integrates yaw into heading penalises coherent biases directly, which is what drives CTE.

Cost: every loss evaluation now requires a trajectory integration per segment. With ~400 segments × Nelder-Mead's ~200 evaluations × an unvectorised integrator, this can blow your time budget. Two prior agents prototyped it; neither finished. Mitigations: use a JIT'd integrator (`numba` is in the environment), subsample to ~50 segments for the loss, or use scipy's `least_squares` with analytic derivatives instead of Nelder-Mead.

Failure mode: if your residual is already bias-corrected (per-segment δ₀ is on), the CTE-aware loss has nothing left to bite on.

## 3. Constrained joint fit of polynomial g and L_eff *[needed if you're combining moves]*

Symptom: you tried polynomial g and the optimiser produced bizarre values (`g₀ = 0.3`, `L_eff = 6.5` — clearly off). One prior agent abandoned polynomial g on Lightning for exactly this reason.

What it is: `g` and `L_eff` are mathematically degenerate at low δ (you can scale them in opposite directions and get the same steady-state yaw rate). Constrain `L_eff` to the wheelbase ± 20% (`bounds=(L_nominal*0.8, L_nominal*1.2)`) when you fit both jointly. Or hold `L_eff` fixed at the `carParams` value and only fit `g`.

Why it helps: removes the degeneracy that turns the optimiser into a random walk.

Cost: one line of bounds in your optimiser call.

Failure mode: if your nominal `L_eff` is far from optimal for one platform, fixing it caps the polynomial-g gain.

## 4. Dynamic single-track with slip angles *[highest upside; highest engineering cost]*

Symptom: after per-segment δ₀ and polynomial g, your residual concentrates in the *transient regime* (segments with high `|d(delta)/dt|`). The first-order yaw lag isn't fitting the dynamics.

What it is: replace the steady-state `yr_ss = v · δ / (L + K_us · v²)` with the actual lateral-dynamics ODE — compute front/rear slip angles `α_f, α_r` from yaw rate and steering, compute lateral force `F = C_α · α`, integrate the yaw-rate equation of motion forward. Needs `C_α_front`, `C_α_rear` per platform (the openpilot priors in `carParams` are known to be off — fit from data).

Why it helps: the steady-state model assumes instantaneous response to steering input. Real vehicles have transient dynamics governed by the slip-angle build-up. In transient-heavy segments this is the residual the first-order lag is band-aiding.

Cost: 50–100 lines of code for the dynamics + integrator. Two extra fitted parameters per platform. Risk of overfit if you can't validate carefully. Probably 2–3× the implementation time of moves 1–3 combined.

Failure mode: if your residual is *not* concentrated in the transient regime (check this first with the regime breakdown from `scoring-model`!), this move buys very little. Several agents named it as the natural next move without first checking whether the data supported it.

## Sequencing if you're going to try more than one

1. Move 1 (fold averaging) is cheap insurance — do this first regardless. Costs ~20 lines, often catches a silent overfit.
2. Move 3 (constrained joint fit) is a one-liner that may rescue polynomial g attempts you've already given up on.
3. Move 2 (CTE-aware loss) only after the above — it's expensive and only pays off if there's coherent bias left to fight.
4. Move 4 (dynamic ST) is the last resort. Only if the transient regime dominates your residual *and* you have time. Don't start here.

You should improve on this if you can.
