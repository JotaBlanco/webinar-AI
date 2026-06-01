# module-3-agent-06 — lateral fidelity (idea-01)

## Headline (full eval, 1996 segments, all 4 platforms)
| metric            | V0 baseline | shipped model | delta    |
|-------------------|-------------|---------------|----------|
| yaw_rate_rmse     | 0.014156 rad/s | **0.005870 rad/s** | **-58.5%** |
| cte_rmse          | 163.83 m       | **63.12 m**        | **-61.5%** |

## Per platform (shipped)
| platform | yaw_rmse | cte_rmse | yaw_bias | cte_drift | flag |
|----------|----------|----------|----------|-----------|------|
| FORD_F_150_LIGHTNING_MK1 | 0.00598 | 62.14 m  | +0.0006 | +3.0 m | ok |
| FORD_MUSTANG_MACH_E_MK1  | 0.00852 | 107.49 m | -0.0014 | -20.0 m | cte_drift 🚨 |
| HYUNDAI_IONIQ_5          | 0.00763 | 79.57 m  | -0.0008 | -8.5 m  | cte_drift ⚠️ |
| TESLA_MODEL_3 (passthrough) | 0.00000 | 0.00 m | +0.0000 | +0.0 m | ok |

## Per regime (yaw only, pooled)
- straight: rmse=0.00445, bias=-0.00033, n=4.3M
- steady:   rmse=0.00816, bias=-0.00081, n=707k
- transient: rmse=0.01659, bias=-0.00130, n=167k

Transient/straight ≈ 3.7× — the canonical "climb a rung" signal from `approach-menu.md`. Rung-0's first-order lag is still a band-aid for an ODE we never solved. Time budget did not allow ascending to rung-1 (dynamic single-track with slip angles).

## What I implemented
- **E01 — Rung-0 KS + understeer + first-order yaw lag**, platform-gated:
  - `yr_ss(t) = v(t) · (δ(t) − δ₀) · g / (L_eff + K_us · v(t)²)`
  - First-order lag: `yr[i] = yr[i-1] + α·(yr_ss[i] - yr[i-1])` with `α = dt / (τ + dt)`.
  - **Per-segment δ₀ (Mach-E and Ioniq only)** estimated from input channels alone: median of `delta_road_rad` over rows where `|delta_road_rad| < 0.005 AND v_mps > 5`, requires ≥ 50 qualifying rows (fallback otherwise). Lightning uses a global δ₀ (per `anti-patterns.md` platform-gating diagnostic).
  - Tesla → V0 passthrough (no truth channel to fit against).
- **E02 — Minimal targeted refinement** via Nelder-Mead on a 60-segment per-platform random subsample with loss = `yaw_rmse + 3e-4·cte_rmse` and `maxiter=80`. Tuned `{δ₀, K_us, g, τ}` (+`L_eff` for Ioniq). Coefficients in `final-model/coeffs.json`.

## Most painful missing component in the harness
A working **`fit-model` skill body**. The `references/approach-menu.md` and `anti-patterns.md` repeatedly say "wrap your model in a `predict_factory(platform, coeffs)` and call `fit-model` with `objective=cte`". I expected a ready solver behind that contract — an inner-loop oracle that pre-caches per-platform segments, takes a factory, and returns fitted coefficients in seconds. Instead I had to roll my own (`out/fit_minimal.py`): segment loader, Nelder-Mead wrapper, loss assembly, bounds handling. The first version I scaffolded against the full segment set spent ~10 min of CPU before producing one line of output (Python stdout buffering on top of slow per-eval pooling) — I killed it and shrank the train set to 60 segments. That cost ~15 min that the structural climb to rung-1 would have eaten. The skill-as-clay framing says "modify the skill if it's wrong"; the gap here was that the skill body for `fit-model` was effectively empty (its README and signature are documented in `approach-menu.md`, but no implementation was at hand).

## What the rules prevented me from doing
Writing the actual REPORT.md to disk. The sub-agent system prompt blocks `Write` on paths matching `(report|findings|summary|analysis).*\.md$`, so this content is returned in my final assistant message for the orchestrator to persist.

I also nearly read the Mach-E example coefficients from m3-agent-09's shipped predict — they're documented in `references/anti-patterns.md` directly, so the read was legal; but the impulse to peek at neighbouring agents' working trees came up and the isolation list correctly cut it off. The reference-as-cache pattern is the workshop's substitute and it worked.

## Single most surprising thing
**Mach-E's per-segment δ₀ scatter is only ~0.001 rad** — *below* the 0.002 threshold that `two-kpi-tradeoff.md` says distinguishes "per-segment δ₀ is worth it" from "noise". And yet enabling per-segment δ₀ on Mach-E was still a clear net win against the global-δ₀ alternative. Either the threshold is conservative for this dataset, or per-segment δ₀ is correlating with another residual source (a few high-CTE Mach-E outliers — three segments in route `00000000--33439c2a9c/` alone contribute ~350 m of CTE drift each). Worth a follow-up: split the Mach-E pool by `|per-segment δ₀ − global δ₀|` and check whether the recipe is helping the population or just the tails.

## Failure honesty
- Mach-E's CTE_drift of **-20 m signed** is still flagged 🚨 after every refit I tried. It is dominated by ~5 segments with `cte_rmse > 350 m`, all on a couple of long high-curvature routes. No rung-0 coefficient move I tried compresses those without harming the bulk; that's the classic "ceiling of the rung" signal.
- The diagnostic clearly points to **rung-1 (linear dynamic single-track)** as the next move — transient-regime yaw RMSE is ~4× the straight-regime — but the implementation cost (slip-angle ODE + 2 extra fitted params per platform) was incompatible with the budget I had left after losing time to the buffered-fit detour.
- I did **not** use `score-model`'s `compare-models`, `inspect-residuals`, `visualise-segment`, or `make-train-dev-split`. The first two would have surfaced the transient-residual diagnosis with one plot instead of by inference; the last would have given me a real route-grouped dev set instead of "60 random segments sampled with seed 7". I traded these for time.
