# Módulo 2 — Bare-harness + memory/state lateral-fidelity report

> **Note on persistence.** Same harness friction as module 1: the agent was blocked from writing this file directly and returned the content in text. Persisted by the workshop facilitator.

## 1. Baseline RMSE ψ̇ (°/s) per platform

| Platform | n_seg | n_rows | RMSE ψ̇ (°/s) | RMSE a_y (m/s²) | mean ψ̇ res (°/s) | corr ψ̇ |
|---|---|---|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | 2 | 5 796 | **0.505** | 0.062 | +0.32 | 0.46 |
| FORD_F_150_LIGHTNING_MK1 | 2 | 5 796 | **1.104** | 0.443 | −0.87 | 0.99 |

(Mach-E correlation looks low only because one of its two segments is highway cruising with near-zero δ; the other Mach-E segment has corr=0.96.)

## 2. Implementations + ablation deltas (mean RMSE ψ̇ °/s)

| Variant | Mach-E | Δ rel | F-150 | Δ rel |
|---|---|---|---|---|
| baseline | 0.416 | — | 1.061 | — |
| +A1 bias correction | 0.087 | **−79%** | 0.619 | **−42%** |
| +A2 steering lag (τ sweep 0–0.4 s) | 0.411 | −1% | 1.052 | −0.8% |
| +A3 wheelbase recal (±15% LS fit) | 0.416 | 0% | 0.954 | −10% |
| A1+A2+A3 stacked | **0.081** | −80% | **0.528** | −50% |

A1 (per-segment yaw bias) dominates and is honestly a sensor-zero calibration, not a model improvement. A3 only delivered on 1 of 4 segments (F-150 `112e…/9`, L_eff = 4.06 m vs canonical 3.70 m — a clean understeer-gradient surrogate). A2 is noise. Did not get to ST model in budget.

## 3. Most load-bearing AGENTS.md rule

**Line 21: "Residual sign convention. `resid = meas − pred`. Always."** Implementing A1, I nearly wrote `bias = median(pred − meas)`, which would have flipped the sign and made the "correction" *worsen* RMSE — I'd have shipped the ranking inverted and called A1 harmful. Runner-up: line 28 ("use the CSV's pre-computed `*_resid_*` columns rather than recomputing") — gave me free cross-validation of the baseline in five minutes.

## 4. Most painful remaining absence

**The skills library (component 6).** I spent ~40% of budget hand-rolling "load CSV, RMSE a column, group by regime, write ablation table" — workflow with nothing module-specific about it. A `skills/lateral-residual-analysis/` skill would have collapsed challenge steps 1–4 into one invocation and left budget for actually implementing an ST model (the upgrade that would have measurably improved the high-G F-150 residual). Memory told me what not to do wrong; skills would have told me how to do the right thing fast. Second-most-painful: evals — I have no automated guard that my A1 sign was right; only the AGENTS.md text rule.

## 5. Most surprising thing about the residuals

Mach-E segment `08ec…/1` is a **near-constant +0.70 °/s offset**: mean +0.700, 95th-pct abs 0.80, RMSE 0.703. The "model error" is almost entirely a DC bias — KS on that segment is *fine*; the truth channel is mis-zeroed (yaw gyro zero / wheel alignment). Inverted, on the F-150 the residual is genuinely high-lateral-G physics: RMSE doubles between 0–1 m/s² (1.05) and 2–4 m/s² (2.16), with mean −2.1 °/s in the 2–4 bin — the car turns **less** than KS predicts at high G, classic understeer. KS is wrong in the way the textbook says it's wrong, and only on the truck.

## Failure honesty

- Did not implement ST model — proposed it, didn't ship it. Time went to ablation tooling.
- A3 only triggered on one segment; the other three had insufficient turning samples to pass the fit mask. Honest aggregate would be "A3 wins where it can win, no-ops elsewhere".
- I did not re-run `generate_simdata_ford.py`; baseline ψ̇_pred from CSVs equals `(v/L)·tan(δ)` analytically and matches the pre-computed column to machine precision, so re-running adds nothing.
- The harness blocked the `REPORT.md` write to module root. All numeric artifacts are in `modulo-2/out/`: `baseline_per_segment.csv`, `baseline_per_platform.csv`, `regime_breakdown.csv`, `ablation.csv`, `ablation_per_segment.csv`, `recalibrated_wheelbase.csv`, `residual_hist.png`, `residual_vs_lat_g.png`, and the reproducible script `baseline_and_ablation.py`.

Reproduce: `python3 out/baseline_and_ablation.py`.
