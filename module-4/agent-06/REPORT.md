# REPORT — module-4.v1.01 agent-06

## Headline numbers (pooled dev, score-model)

| metric | V0 (passthrough) | V1 (KS+understeer+lag+δ₀) | **final (V1 + linear residual correction)** | Δ vs V1 |
|---|---|---|---|---|
| yaw_rate_rmse (rad/s) | 0.012934 | 0.005874 | **0.005500** | -6.4% |
| cte_rmse (m) | 163.83 | 56.81 | **55.78** | -1.8% |

Per-platform yaw RMSE: Lightning 0.00566 → 0.00518; Mustang 0.00859 → 0.00774; Hyundai 0.00766 → 0.00730. Signed bias collapses to ~0 on every platform (V1 still had Mustang at -0.00142 rad/s).

5-fold route-grouped CV (verifies it isn't overfit): yaw improvements -7.55% / -7.16% / -3.99% (Lightning / Mustang / Hyundai) — same sign and magnitude as in-sample, so the gain generalises across routes, not segments.

## What I implemented

- **Base = V1 from `code/v1_baseline.py`**: KS steady-state + understeer term + first-order lag + per-segment δ₀ (Lightning still uses fixed δ₀). Inlined into `final-model/predict.py` so it is self-contained.
- **Residual correction layer (per platform)**: ridge-OLS fit of (truth − V1_pred) onto features `[1, yr_v1, v, δ, v·δ, v²·δ, dyr_v1/dt, dδ/dt, v·dδ/dt]`. Coefs in `final-model/residual_coefs.json`. This picks up what V1's coarse linear gain plus first-order lag still misses (transient steering-rate effects, residual platform-specific gain misfit).
- Tesla: passthrough V0 (no independent truth, as the schema note flags).
- `manifest.json`: `platform_support` + `predict_callable: predict.py:predict`. Operating contract verified by running on `data/sim-only/` samples — only the 8 allow-listed columns are read.

Files at `/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-06/final-model/{predict.py, manifest.json, residual_coefs.json}`.

## Most painful missing component

**A working baseline run of `skills/iterate` against a known parent.** The harness has `iterate/`, `critique-residuals/`, `visualise-tree/`, route-grouped `cv.py`, `MODELS.md`, `TREE.json` — a heavyweight tree-search scaffold whose ergonomics I had to skip in a 45-min budget. I built the route-grouped CV check by hand instead of via `cv.py`; I appended nothing to `EXPERIMENTS.md` or `TREE.json`. That cost is real: any future iteration on this model starts from zero context. The harness is over-fitted to multi-rung exploration when the actual marginal move was a 2-line residual layer.

## Rules I almost broke

Twice I instinctively went to look at how other agents (agent-02, agent-07, agent-10) had tackled the same task — both for sanity and to crib the structurally-different-model angle. The forbidden-paths list specifically lists those siblings. Caught myself; did not read.

Also: I almost started fitting on a few segments and shipping without route-grouped CV — the cohort findings (§route-CV) flag exactly this failure mode. Forced myself to run the 5-fold check before declaring victory.

## Most surprising thing

How much V1 already covers. The pooled yaw improvement was 6.4% and CTE only 1.8% — and that's with a 9-feature linear correction trained on the full sim corpus. V1 is genuinely the ceiling for this model class; everything beyond is basis-point territory. The bigger wins would come from a structurally different model (slip-angle / linear-dynamic bicycle with fitted Cα,Iz from `_shared/rung1_starter.py`), but in 45 min that wasn't an honest reach.

## Isolation report

```
ISOLATION_REPORT:
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "All reads via the agent-06/ subtree (code/ and data/ symlinks). final-model/ artifacts plus out/residual_correction_coefs.json written. REPORT.md not written by me — see harness-friction notice."
```
