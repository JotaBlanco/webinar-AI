# Implement notes

Ran `tools/run_ladder.py` on FORD_MUSTANG_MACH_E_MK1, 315 segments, 913,626 samples (test fold 182,725).

## Surprises vs plan

- **V1 (bias removal)** came in as a **regression of -0.00001 rad/s** on the held-out test set. Median residual on train is +0.00075 rad/s — small enough that on test it slightly *worsens* (it was already centred enough that the small bias term hurt the straight regime by 3e-5). Falsifier confirmed: there is no DC component worth removing. Kept on the ladder per ablation-study discipline.
- **V2 (lag alignment)** best lag came out at **k=0** (zero ms shift). Hypothesis falsified at the 20 ms grid: openpilot's `delta_road_rad` and the IMU yaw rate appear already aligned by the upstream pipeline. Marginal +0.00000.
- **V3 (effective wheelbase)** delivered virtually all the improvement: L_eff = **2.793 m**, ~6.4% shorter than the canonical L = 2.984 m. Overall RMSE 0.01613 → 0.01557, transient 0.0571 → 0.0511, steady 0.0316 → 0.0298.

## Tradeoff observed

V3 increases the **straight** regime RMSE from 0.00872 → 0.00944 (+8%). Physical reason: a shorter L_eff also amplifies any tiny δ noise around zero, so a near-straight road's small δ jitter gets gained up. Not flagged as a ladder regression because the overall and cornering improvement dominates — but it is a real tradeoff to call out. A future V4 could gate the L_eff correction on a cornering mask.

## Attribution

| Variant | overall | marginal Δ |
|---|---|---|
| V0 | 0.01613 | — |
| V1 bias | 0.01613 | -0.00001 (regression) |
| V2 lag k=0 | 0.01613 | +0.00000 |
| V3 L_eff=2.793 | 0.01557 | +0.00056 |

Σ marginals = +0.00055; total drop = +0.00055; coherence err = 0.0000 (well under 0.15). 

## Deviations from plan

None. Order locked V1→V2→V3 was preserved. V1's regression and V2's null result were reported, not silently dropped.

## Artifacts

- `out/ladder_summary.json` — full numerics
- `tools/run_ladder.py` — the ladder

## Schema check

V0 numbers match `evals/baseline_rmse.py` exactly. The variant predictions are not re-emitted as CSVs (the ablation runs in-memory off the existing sim.csv truth columns), so `schema_check.py` was not re-invoked on derived CSVs; the source sim.csvs are presumed schema-valid (used by the eval script which passed).
