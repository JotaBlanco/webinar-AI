# EXPERIMENTS.md

Append-only log.

---

## E00 — V0 baseline (pass-through)
- Rung: 0
- Hypothesis: establish the floor.
- What I changed: nothing — predict() returns sim_df["yaw_rate_pred_rads"].
- Result (full set, all 4 platforms):
  - **yaw_rmse: 0.01361 rad/s**
  - **cte_rmse: 163.83 m**
  - Per platform: Lightning yaw 0.0163 / cte 157; Mach-E yaw 0.0136 / cte 148; IONIQ-5 yaw 0.0177 / cte 247; Tesla 0 (no truth).
  - Bias warnings: cte_drift HIGH on Lightning (+39.7 m) and IONIQ-5 (-54.8 m).
- Verdict: baseline.

## E01 — V1: KS + understeer + first-order lag + per-segment δ₀ (platform-gated)
- Rung: 0
- Hypothesis: the highest-leverage move from references/anti-patterns.md §
  "The legal cousin". Per-segment δ₀ from straight-row median + understeer
  (K_us) + first-order lag, gated per-platform.
- What I changed vs E00:
  - δ' = (delta_road_rad − δ₀_seg) · g; yr_ss = v · δ' / (L_eff + K_us · v²); first-order lag (τ).
  - δ₀ estimated per segment from rows where |yr_v0| < 0.03 ∧ v > 5 (≥50 rows).
  - Gated ON for Mach-E + IONIQ-5; OFF for Lightning; Tesla → V0 passthrough.
  - Coeffs fit per-platform with `fit-model` (objective: yaw_plus_cte,
    L-BFGS-B, bounded), route-grouped 75/25 train/dev split.
  - Fitted: Lightning {g=0.838, L_eff=3.27, K_us=0.00309, τ=0.063, δ₀=0.0014};
    Mach-E {g=0.869, L_eff=2.23, K_us=0.00154, τ=0.048, per-seg δ₀};
    IONIQ-5 {g=0.904, L_eff=2.91, K_us=0.00217, τ=0.022, per-seg δ₀}.
- Result (full set, all platforms pooled):
  - **yaw_rmse: 0.00608 rad/s  (−55% vs V0)**
  - **cte_rmse: 55.85 m         (−66% vs V0)**
  - Per platform:
    - Lightning: yaw 0.0060 (−63%), cte 60.8 (−61%)
    - Mach-E:    yaw 0.0086 (−37%), cte 98.7 (−33%)
    - IONIQ-5:   yaw 0.0080 (−55%), cte 67.6 (−73%)
    - Tesla:     unchanged (passthrough).
  - Bias warnings: Mach-E cte_drift −21.8 m (still HIGH); IONIQ-5 −12.5 m (WARN); Lightning ok.
  - Fit warning: Mach-E train/dev gap +54% — high variance from only 13 Mach-E routes; in-pool RMSE still well below V0.
- Verdict: ship.
- Things this rules out: V0's biggest gap is per-segment steering offset and understeer scaling, not transient dynamics.

## E02 — Rung 1: linear dynamic single-track (Mach-E only, cheap version)
- Rung: 1
- Hypothesis: V1 leaves Mach-E weakest (yaw 0.0086 / cte 98.7). A state-space
  single-track with slip angles models transient lateral dynamics that V1's
  first-order lag only band-aids. Recipe from references/dynamics-formulations.md
  § "Rung 1": fit C_af only, fix {m, Iz, a, b, C_ar} from MachEST carParams.
- What I changed vs E01: predict shape replaced with two-state Euler on
  (vy, yr), 4 sub-steps per sample to stabilise at low vx; defensive clamps
  on |vy|, |yr| to avoid runaway. Manual grid sweep over C_af on Mach-E
  train-subset (40 segs) because L-BFGS-B returns zero finite-difference
  gradient on this noisy objective.
- Result (Mach-E, train-subset, sweep over C_af):
  - C_af=80k → yaw 0.0195; 120k → 0.0166; 160k → 0.0148; 200k → 0.0136;
    250k → 0.0128; 300k → **0.0125 (best)**; 400k → 0.0128.
  - Comparison: V1 (E01) on the FULL Mach-E set = **0.0086** yaw RMSE.
  - **Rung 1 is ~45% worse than V1's rung 0 on Mach-E.**
- Verdict: revert. Rung 0 + per-segment δ₀ wins.
- Things this rules out:
  - Two-state slip-angle dynamics with a single fitted C_af (carParams-fixed
    elsewhere) does NOT beat rung 0 + per-segment δ₀ on Mach-E.
  - The cohort evidence for "does rung 1 help on this dataset?" is: at the
    cheap end of the rung-1 ladder, no. A higher-effort rung 1 would need
    (a) C_ar, m, Iz also free, AND (b) the per-segment δ₀ recipe layered
    on top — without that, the bias source rung 0 fixes is left on the table.
  - Concrete costs encountered: integrator stability at low vx forced
    sub-stepping (~4x cost per evaluation); finite-difference optimisation
    returned zero gradient, forcing manual sweep.
