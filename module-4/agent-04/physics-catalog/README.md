# physics-catalog — pre-built physics models, beyond V1's kinematic bicycle

**Eight** working physics models, ready to copy into `models/<name>/` and
iterate. Each one is structurally different from V1 — not a coefficient
variation. The catalog exists because the m4.v1 cohort showed that 80%
of agents converged on V1-with-different-coefficients regardless of
`launch-rungs/`'s rung instructions; the bottleneck was that **no
rung-1+ code was actually on disk**. This fixes that.

When the 8 don't fit your residual, build the 9th —
[`../references/build-your-own-model.md`](../references/build-your-own-model.md)
names the 4 dimensions of structural diversity and sketches 8 more model
ideas the cohort hasn't tried.

## The eight models

| dir | rung | structure | fitted params per platform | attacks |
|---|---|---|---|---|
| [`dst_lin/`](dst_lin/notes.md)                         | 1 | Linear-tyre dynamic single-track                            | C_αf, C_αr, I_z                                | transient regime — cohort §1 + §7 |
| [`dst_nl/`](dst_nl/notes.md)                           | 2 | Pacejka-lite saturating tyre on dst_lin                     | + μ, C                                          | high-α segments — cohort §8 |
| [`dst_regime/`](dst_regime/notes.md)                   | 1 | Smooth-blend kinematic ↔ dst_lin by \|v·ψ̇\|                  | + θ, blend_width                                | "rung-1 only where it earns" — cohort §1 |
| [`dst_relax/`](dst_relax/notes.md)                     | 2 | dst_lin + per-axle tyre relaxation length σ                 | + σ_relax                                       | physics-justified lag — cohort §8 |
| [`dst_load/`](dst_load/notes.md)                       | 3 | dst_lin + a_long-induced axle load transfer                 | + h_cg                                          | Lightning brake-into-corner — cohort §2 + §9 |
| [`dst_twin_track/`](dst_twin_track/notes.md)           | 2 | 4-wheel twin-track + lateral load transfer                  | + h_cg, track_width, k_LLT_f                    | cornering load transfer — Lightning, fast curvature |
| [`dst_combined_slip/`](dst_combined_slip/notes.md)     | 2 | Friction-circle F_x × F_y coupling                          | + μ, α_drive                                    | brake-into-corner saturation (mechanism distinct from dst_load) |
| [`dst_steer_compliance/`](dst_steer_compliance/notes.md) | 2 | Steering compliance + Ackermann split (closed-form fixed point) | + K_compl, k_ackermann                          | "is V1 lag mis-modelling compliance?" — cohort §8 alt |

For "which model attacks which residual character" mapping, see
[`../references/physics-menu.md`](../references/physics-menu.md).

## How each subdir is laid out

```
physics-catalog/<model_name>/
├── __init__.py
├── predict.py            ← the model. predict(sim_df, platform) -> DataFrame
├── fit.py                ← refit on the project's dev split under route-grouped CV
├── coeffs.default.json   ← textbook priors (work out of the box, NOT fitted on dev)
├── notes.md              ← rung tag, parent, expected_residual, ## What this differs from
└── smoke.py              ← synthetic-data smoke test (no data/ dependency)
```

Plus the shared layer:

```
physics-catalog/
├── _common.py            ← per-platform priors, RK4 steppers, route-grouped fitter
└── _audit.py             ← exercises every skill × every model
```

## How to use one

```bash
# 1. Copy a catalog model into models/<your-name>.
cp -r physics-catalog/dst_lin models/dst_lin-baseline

# 2. (Recommended) refit on your dev split — defaults are textbook priors.
python -m physics-catalog.dst_lin.fit
cp physics-catalog/dst_lin/coeffs.json models/dst_lin-baseline/coeffs.json

# 3. Run iterate. The novelty gate, route-CV gate, and bias gate all pass
#    for catalog models out of the box.
python -m skills.iterate.iterate models/dst_lin-baseline
```

Note: `notes.md` in each catalog model already contains the `## What this
differs from` section the iterate novelty gate requires. When you copy
into `models/`, that section transfers — so you don't have to write the
novelty bullets from scratch. Edit it to be specific about your version
(what you changed in your iterated bundle vs the catalog start).

## Why the defaults are textbook, not fitted

The catalog ships with `coeffs.default.json` containing **physically-
plausible textbook values** per platform (e.g. Lightning at I_z=6000,
h_cg=0.85 m). These are NOT fitted on the project's dev split — fitting
would require running `fit.py` with `data/` populated, which only happens
in the project environment.

Result: every catalog model runs out of the box (the smoke tests prove
it) but **doesn't necessarily beat V1 until refit**. The first move when
you copy a catalog model is `python -m physics-catalog.<name>.fit`. The
fitter is real and complete; it writes route-CV σ into the new
`coeffs.json` automatically.

## Compatibility with the m4.v1.01 skill stack

| skill                       | catalog compatibility |
|---|---|
| `skills/score-model`        | works — every model's predict matches the operating contract |
| `skills/score-model/cv.py`  | works — used by every model's `fit.py` |
| `skills/fit-model`          | works — but catalog models prefer their own `fit.py` because the parameter space is model-specific |
| `skills/residual-structure` | works — model-agnostic |
| `skills/assess-candidate-model` | works — model-agnostic |
| `skills/critique-residuals` | works; routes already aware of rung 1+ outcomes |
| `skills/iterate`            | works — catalog models are valid bundle inputs |
| `skills/pre-flight-final-model` | works — catalog `coeffs.default.json` does NOT declare bias terms, so the bias_without_route_cv gate is vacuous; if a derived model adds bias, `fit.py` writes `route_cv_sigma` automatically |
| `skills/compare-models`     | works — model-agnostic |

Run the audit to confirm in your environment:

```bash
python -m physics-catalog._audit              # synthetic mode (always works)
python -m physics-catalog._audit --real       # add real-data score-model check
```

## Adding a 6th model

1. `mkdir physics-catalog/<new_name>/`
2. Write `predict.py` matching the contract (read 8 allowlist columns,
   return DataFrame with `yaw_rate_pred_rads`). Use helpers from
   `_common.py` (RK4 steppers, parameter priors).
3. Write `fit.py` using `_common.fit_with_route_cv` — supply a `FitSpec`
   with init/bounds/names for your fitted params.
4. Write `coeffs.default.json` with textbook priors.
5. Write `notes.md` — include rung, parent, expected_residual, and a
   `## What this differs from` section.
6. Write `smoke.py` — synthetic segments, asserting finite output across
   platforms.
7. Add a row to this README's table and the `references/physics-menu.md`
   cross-table.
8. Run `python -m physics-catalog._audit` — must be 100% green.
