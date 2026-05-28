# Module-4 / agent-01 (angle-C) — Lateral fidelity ladder

**Headline:** A per-platform bias + scalar gain on `yaw_rate_pred_rads` drops held-out RMSE 2.4% on Mustang Mach-E and **19.0% on F-150 Lightning**. Gain is the load-bearing variant on both cars; bias matters only on F-150; a uniform 1-sample lag shift is a regression on both.

## Variants (test RMSE rad/s, interleaved every-5th split, per-platform fits)

**Mustang Mach-E** (V0=0.01613 → V3=0.01575, coherence 0.000)

| # | variant | overall | Δ | straight | steady | transient |
|---|---|---|---|---|---|---|
| V0 | baseline | 0.01613 | — | 0.00878 | 0.03147 | 0.05743 |
| V1 | +bias=0.00075 | 0.01614 | +0.00001 **REGRESSION** | 0.00874 | 0.03155 | 0.05750 |
| V2 | +gain=1.069 | 0.01558 | -0.00056 | 0.00947 | 0.02966 | 0.05148 |
| V3 | +lag1 (per-seg) | 0.01575 | +0.00017 **REGRESSION** | 0.00954 | 0.02970 | 0.05298 |

**F-150 Lightning** (V0=0.02037 → V3=0.01651, coherence 0.000)

| # | variant | overall | Δ | straight | steady | transient |
|---|---|---|---|---|---|---|
| V0 | baseline | 0.02037 | — | 0.00899 | 0.03629 | 0.05161 |
| V1 | +bias=0.00442 | 0.02006 | -0.00031 | 0.00799 | 0.03634 | 0.05161 |
| V2 | +gain=0.859 | 0.01635 | -0.00372 | 0.00629 | 0.02854 | 0.04519 |
| V3 | +lag1 | 0.01651 | +0.00016 **REGRESSION** | 0.00638 | 0.02855 | 0.04624 |

**Recommended ship: V2 per-platform.** Bias and gain belong in `PARAM_BY_PLATFORM`.

## Painful absence

None acutely felt — `baseline-residual` and `ablation-study` covered the run. Sub-sample lag would have been worth a skill, but only one variant exercised it.

## Near-miss

V3 lag wobbled near zero; an integer-sample shift over-corrected sub-sample lag → flagged regression rather than dropped.

## Surprise

`evals/schema_check.py` **FAILS** on every source `sim.csv` — stored `yaw_rate_resid_rads` equals `meas − pred` (matches to 8.9e-07), not `pred − meas` as the convention in AGENTS.md/CLAUDE.md states (max diff 9.79e-02). RMSE is sign-symmetric so V0 numbers are unaffected, but Ratchet item #1 (the encoded past failure) is **currently present in the data on disk**. My variants recompute residual fresh, so are correct under the documented convention.

## Cross-platform finding

Gains have opposite direction — Mustang KS *under*-predicts (1.069), F-150 KS *over*-predicts (0.859). A global gain is useless; per-platform is mandatory.

## a_y coupling

`a_y_pred = v·ψ̇_pred` propagates the gain correction one-to-one; did not refit `a_y` separately.

## RPI artifact paths

- `rpi/runs/20260527-155947/research.md`
- `rpi/runs/20260527-155947/plan.md` (LOCKED pre-implementation)
- `rpi/runs/20260527-155947/implement-notes.md`
- Tool: `tools/ablate_lateral.py`
- Outputs: `out/ablate_FORD_MUSTANG_MACH_E_MK1_20260527-160123.{csv,json}` and `…F_150_LIGHTNING_MK1_20260527-160129.{csv,json}`

## Eval status

- `baseline_rmse.py` Mustang+F-150 → V0 matches my V0 to 5 dp ✓
- `schema_check.py` → **FAIL** on every source sim.csv (pre-existing data convention bug)

## Skills used

- `baseline-residual` (metadata + cross-checked via `evals/baseline_rmse.py`)
- `ablation-study` (discipline implemented in `tools/ablate_lateral.py`)
- **No new skill authored** — no recurring procedural gap appeared.
