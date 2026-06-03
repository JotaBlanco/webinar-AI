# Module-4.v2.01 — agent-05 — REPORT

## Summary

**Headline: yaw_rate_rmse = 0.005430 rad/s, CTE_rmse = 52.215 m on the 402-segment dev split.** Shipped V1 baseline (rung-0, m3.v3 converged coefficients) at `final-model/predict.py`. Operating contract verified on `sim-only/segments/` (8-col allowlist, no truth reads).

**What I implemented (and why the ship is V1, not M4):**
- **M4 relaxation-length (rung-1 orthogonal)** — distance-domain first-order lag replacing V1's tau lag, per-platform sigma fit on dev (F150=0.30, MachE=0.35, Ioniq5=0.25). Result: yaw=0.005610 / CTE=52.10. Loses to V1 by **+3.3% yaw** while winning CTE by only 0.12 m (within noise). Shelved.
- **V1 baseline (rung-0, shipped)** — kinematic single-track + understeer K_us + first-order tau lag + per-segment delta0. Beats M4 on yaw across all three Ford/Hyundai platforms.

**Sigma sweep over {0, 0.10, 0.30, 0.35, 1.0}** confirms no setting beats V1 on pooled yaw, so the M4 mechanism is the wrong axis here — V1's tau already captures the relevant phase lag.

**The prior session's manifest was misleading**: it claimed V1=0.005706 (citing the static MODELS.md figure of 0.005874) and called M4=0.005618 a win. On the same scoring run, V1 is actually 0.005430. I corrected the ship.

**Most painful missing component**: a *time-aware honesty harness*. The previous session shipped, wrote a manifest, then ran out of budget — and I inherited a stale "winning" model nobody re-validated. A 10-line "scorecard-on-resume" autocheck (re-run V1 + shipped model on dev, fail loudly on regression) would have caught this in the first 30 seconds.

**Almost did but the rules stopped me**: I almost re-ran the prefilled M1/M2/M3/M5 dynamics-ladder fits (the unfit rung-1/2/3 candidates) in `phases/3-implement/models/<m>/fit.py`. Time budget would have allowed maybe one, and the cohort prior says zero of 90 agents have shipped rung-1. I deferred and shipped V1 honestly instead. The strict isolation rules also stopped me from peeking at other agents' work to see whether any of them got M3 (load transfer) to work on F150.

**Single most surprising thing**: the dev-split V1 yaw (0.005430) is meaningfully lower than the MODELS.md "truth of record" (0.005874) — a ~7.5% gap. Different scoring contexts produce different V1 numbers, which means anyone comparing across sessions without re-running V1 in their *own* context will get fictional vs-V1 deltas. The M4 author hit exactly that trap.

**Files of record:**
- `final-model/predict.py` (V1, self-contained, 8-col allowlist)
- `final-model/coeffs.json` (V1 coeffs + shelved M4 sigmas as note)
- `final-model/manifest.json` (updated metrics)
- `MODELS.md` (M4 marked shelved, V1 marked shipped)

---

ISOLATION_REPORT:
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "All reads confined to module subtree + code/ + data/ symlinks. No writes to shared dirs."
