# EXPERIMENTS.md

Append-only log of approaches you tried. One entry per concrete attempt. See `references/exploration-discipline.md` for the why.

Schema:

```
## E<NN> — <one-line approach name>
- Hypothesis: why you thought this would help, in one line.
- What I changed vs E<NN-1>: the minimal diff.
- Result (dev): yaw <old> → <new> (Δ%); CTE <old> → <new> (Δ%).
- Verdict: keep | revert | revisit-later.
- Things this rules out: what you learned, even if the experiment failed.
```

Delete this header section once you start logging, but keep the schema close to mind.

---

## E00 — V0 baseline (no changes)
- Hypothesis: establish the floor we're trying to beat.
- What I changed vs nothing: nothing — predict() passes through `yaw_rate_pred_rads`.
- Result (dev, all 4 platforms, score-model defaults): yaw 0.012934; CTE 163.831.
- Verdict: baseline.
- Notes: Lightning has yaw_bias +0.0041 / cte_drift +39.7 m; Hyundai yaw_bias -0.0036 / cte_drift -54.8 m. Mach-E nearly balanced. Tesla zero (psi_dot IS V0).

## E01 — Per-platform refined KS: (g, delta0, K_us, tau, L_eff) + first-order lag
- Hypothesis: Lightning + Hyundai have large signed biases — a per-platform fit of steering scale, offset, understeer, and lag should erase the bias and capture steady cornering nonlinearity. Tesla → V0 passthrough (no truth).
- What I changed vs E00: fitted 5 coeffs per platform via Nelder-Mead on pooled v-filtered yaw sum_sq using all Lightning (175 segs) + all Mach-E (240 segs) + first 200 Hyundai segs. Vectorised lag via scipy.signal.lfilter (mean dt).
- Result (dev): yaw 0.012934 → 0.006403 (-50.5%); CTE 163.831 → 83.322 (-49.1%).
- Verdict: keep, ship.
- Things this rules out / limitations: per-segment δ₀ in the legal recipe in `anti-patterns.md` depends on `a_lat_meas_mps2`, which is NOT in the operating-contract input columns — so could not use that recipe as written. Hyundai still has cte_drift -27 m; would need a Hyundai-specific second pass (e.g. polynomial g, or higher K_us at low speed). Lightning fitted g=0.60 / L_eff=2.27 may be on the g↔L_eff scale-invariance ridge but the optimum is real because K_us also moved.
