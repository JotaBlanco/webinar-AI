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
- Result (full dev): yaw 0.01293; CTE 163.83 (pooled across 4 platforms).
- Verdict: baseline.

## E01 — Per-platform refined KS: (g, L_eff, K_us, tau) + platform-gated per-segment δ₀
- Hypothesis: V0 leaves per-platform structural residual; refining coefficients per platform plus per-segment δ₀ on platforms with wide bias spread should close most of it.
- What I changed vs E00: built `predict()` that branches per platform; Tesla stays V0 passthrough (no truth). Mach-E and Hyundai use per-segment δ₀ (detected with |delta_road_rad|<0.005 + v>8 m/s — a_lat_meas not in sim-only allowlist so couldn't use the canonical recipe). Lightning uses a global δ₀. Fitted with Nelder-Mead on a composite loss yaw/0.01 + 0.5·cte/50 over ~150 segments/platform.
- Result (full dev): yaw 0.01293 → 0.00587 (-54.6%); CTE 163.83 → 63.01 (-61.5%).
- Verdict: keep. Hits the task contract; per-platform breakdown shows Mach-E (107 m CTE) is the next bottleneck.
- A/B sanity: per-segment δ₀ helps Hyundai (cte 102 vs 148 global) and Mach-E; hurts Lightning (cte 60 vs 122) — confirms platform-gating rule from anti-patterns.md.
- Things this rules out: Hyundai needs per-segment δ₀ just like Mach-E (anti-patterns doc didn't have Hyundai numbers).
