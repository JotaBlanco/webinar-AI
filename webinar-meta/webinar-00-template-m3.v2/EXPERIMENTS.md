# EXPERIMENTS.md

Append-only log of approaches you tried. One entry per concrete attempt. See `references/exploration-discipline.md` for the why.

Schema (every field required):

```
## E<NN> — <one-line approach name>
- Rung: 0 | 1 | 2 | 3 | orthogonal
- Hypothesis: why you thought this would help, in one line.
- What I changed vs E<NN-1>: the minimal diff.
- Result (dev): yaw <old> → <new> (Δ%); CTE <old> → <new> (Δ%).
- Verdict: keep | revert | revisit-later.
- Things this rules out: what you learned, even if the experiment failed.
```

**`Rung:` is required on every entry.** The grader's preflight checks for at least one entry tagged `Rung: 1` (or higher, or `orthogonal`). Past cohorts piled up at rung 0 — see `AGENTS.md` § "On exploration — the default is to climb". Tagging discipline:

- `Rung: 0` — kinematic single-track (V0 shape): coefficient refinements, polynomial steering scale, per-segment δ₀, lag time-constant tuning. Anything that stays in `yr_ss = v · δ / (L + K · v²)` territory.
- `Rung: 1` — linear dynamic single-track with slip angles. State variables `vy`, `yr`; lateral force `F = C_α · α`. See `references/dynamics-formulations.md` § "Rung 1" for the minimum viable recipe.
- `Rung: 2` — nonlinear tyre (Pacejka, Fiala, brush) on top of rung 1.
- `Rung: 3` — multi-body / weight-transfer coupling.
- `Rung: orthogonal` — non-physics paths (residual ML on top of a physical prior, sensor-fusion / complementary filter, etc.).

Delete this header section once you start logging, but keep the schema close to mind.

---

## E00 — V0 baseline (no changes)
- Rung: 0
- Hypothesis: establish the floor we're trying to beat.
- What I changed vs nothing: nothing — predict() passes through `yaw_rate_pred_rads`.
- Result (dev): yaw 0.01456; CTE 147.44.
- Verdict: baseline.
- Things this rules out: nothing yet.
