# Módulo 4 — Full harness — lateral-fidelity report

> **Note on persistence.** Same sub-agent harness friction across all 4 modules: the agent could not write this file directly. Content returned in text; persisted by facilitator. Full content also captured in `rpi/runs/20260526-010056/implement-notes.md`.

## 1) Baseline RMSE ψ̇ (°/s) per platform

| Platform | RMSE ψ̇ (°/s) | RMSE a_y (m/s²) | corr ψ̇ |
|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | **0.4155** | 0.0613 | 0.877 |
| FORD_F_150_LIGHTNING_MK1 | **1.0607** | 0.4042 | 0.958 |

Verified to agree between `skills/baseline-residual/compute.py` and `evals/baseline_rmse.py`.

## 2) Implementations + ablation deltas

| Variant | F-150 RMSE ψ̇ | Δ% | Mach-E RMSE ψ̇ | Δ% |
|---|---|---|---|---|
| baseline | 1.0607 | — | 0.4155 | — |
| +A (per-platform yaw bias) | 0.6654 | **−37.3 %** | 0.3943 | −5.1 % |
| +A +B (understeer-gradient) | 0.6240 | **−41.2 %** | 0.3769 | −9.3 %\* |

Fitted params: bias F-150 = −0.01524 rad/s; Mach-E = +0.00551 rad/s. Understeer k F-150 = +0.0237 1/(m/s²); Mach-E = **+1.0 boundary (overfit, unidentifiable)**. F-150 corr(yaw_resid, |a_y|) drops from −0.13 to +0.115 — physical success criterion met.

\* Mach-E +B is bogus (|a_y|≈0 makes k unidentifiable); honest read is +B helps F-150 ~4 pp, Mach-E 0.

## 3) Skills loaded (metadata-first observation)

- **`baseline-residual`** body — loaded in phase 1 to run the baseline. Verified against `evals/baseline_rmse.py`.
- **`yaw-bias-correction`** body — loaded in phase 3 to produce variant A.
- **`ablation-study`** body — loaded in phase 3 to produce the table.

All three SKILL.md frontmatters were short enough that the agent read them in full; metadata alone could have let it skip the bodies of `ablation-study` and `yaw-bias-correction` until phase 3, which it effectively did. The harness's metadata-first promise held — no skill body loaded eagerly.

## 4) New skill authored on the fly

**`skills/sim-csv-hygiene/`** — recomputes `yaw_rate_resid_rads` and `a_y_resid_mps2` from `meas − pred` at full precision and rewrites CSVs with `float_format='%.10g'`, so `schema_check.py` passes after any CSV round-trip. Triggered by a real recurrent failure (see §5). Reused 3× across variants.

## 5) Did evals + RPI + skills catch anything?

**Yes, two things:**
- `schema_check.py` **FAILed 3/4 baseline CSVs** with `a_y_resid sign wrong (max diff 1.0e-06)` — a float round-trip at the exact 1e-6 tolerance boundary. Without the sensor, the agent would have shipped variants with subtly drifted residual columns. Triggered the new `sim-csv-hygiene` skill.
- The plan's **pre-committed physical criterion** (corr(resid,|a_y|) must drop on F-150) exposed the Mach-E `k=1.0` boundary overfit — that "−9.3% Mach-E" delta looks legitimate in a bare table and would have been reported as a real win. Plan discipline outed it.

## 6) Component that earned the most of its keep

**Verification (evals)**, specifically `schema_check.py` running on every variant dir. Without it the FP round-trip would have silently propagated across all three variants. RPI was a close second — splitting research from plan saved time on an actuator-lag fix the data didn't support. Skills/modularity earned the *least* of its keep on this specific challenge size (each skill is ~50 lines); the value showed up only when the new `sim-csv-hygiene` skill got reused 3×.

## 7) Most surprising thing about the residuals

**F-150 baseline residual is ~80% bias by power** — `mean(resid)² / RMSE² ≈ 0.87² / 1.06² ≈ 0.68`. The "complicated" kinematic-vs-real-tyre story expected turned out to be mostly a constant calibration offset. Prediction shape is already very good (corr 0.96 baseline). The Mach-E surprise is the *opposite*: lower RMSE in absolute terms but worse correlation (0.877) — small signals, ugly shape match.

## Artifacts on disk

- RPI artifacts: `rpi/runs/20260526-010056/{research,plan,implement-notes}.md`
- Variant CSV dirs: `out/sim_baseline/`, `out/sim_+A_bias/`, `out/sim_+A+B_understeer/` (all pass schema_check after sim-csv-hygiene)
- New skill: `skills/sim-csv-hygiene/SKILL.md`, `skills/sim-csv-hygiene/normalise.py`
- Variant-B implementation: `out/apply_understeer.py`
