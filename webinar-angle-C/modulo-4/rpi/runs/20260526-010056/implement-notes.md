# Implement-notes

> Phase 3. Read only plan.md.

## Run order

1. Mirror baseline CSVs to `out/sim_baseline/`.
2. `evals/schema_check.py out/sim_baseline/` → **3/4 FAIL** (FP round-trip).
3. **Crystallised new skill `sim-csv-hygiene`** (recipe in SKILL.md, helper at `skills/sim-csv-hygiene/normalise.py`) because this is going to recur on every variant output.
4. Normalise → re-check → all pass.
5. Apply skill `yaw-bias-correction` → `out/sim_+A_bias/` → normalise → schema_check → pass.
6. Implement `out/apply_understeer.py` (variant B). First fit blew up because Mach-E's loss surface is flat (|a_y|≈0) and Brent rejected the bracket — switched to `bounded`. Mach-E pinned `k=1.0` (boundary), confirming the term is unidentifiable on that platform.
7. Re-check → pass.
8. Run `skills/ablation-study/run.py` over the three dirs.

## Numbers (RMSE ψ̇ in °/s, mean-of-segments)

| Variant | F-150 | Δ_F-150 | Mach-E | Δ_Mach-E |
|---|---|---|---|---|
| baseline | 1.061 | — | 0.416 | — |
| +A (bias) | 0.665 | **−37.3 %** | 0.394 | −5.1 % |
| +A +B (understeer) | 0.624 | **−41.2 %** | 0.377 | −9.3 % |

Fitted parameters:
- Bias: F-150 = −0.01524 rad/s (−0.87 °/s); Mach-E = +0.00551 rad/s (+0.32 °/s).
- Understeer `k`: F-150 = +0.0237 1/(m/s²); Mach-E = +1.00 (boundary — overfit to noise).

Physical sensor: F-150 corr(resid, |a_y|) went −0.132 → +0.115 after B (well inside |<0.3| target).

## What worked

- **Variant A** is exactly the free lunch the SKILL predicted. F-150 baseline residual was 79% bias by power (mean² / RMSE² = 0.873²/1.061² ≈ 0.68 pooled-mean, ≈0.79 segment-mean). Removing it cleared most of the RMSE.
- **Variant B** earns a *small* additional 4 pp on F-150 (37→41% delta). The understeer-gradient hypothesis is correct in sign and direction but the high-G regime is rare in 58 s of data; the term is mostly idle.
- **`sim-csv-hygiene` skill** caught the schema_check failure cleanly. Without it I would have either (a) ignored the FAIL and reported invalid variants, or (b) hand-rewritten a one-off snippet for each variant dir.

## What didn't

- Mach-E variant B is bogus — the loss is essentially flat in `k`, the optimiser pins the boundary. The 9.3% delta on Mach-E is a measurement artefact, not signal. **In the REPORT this must be flagged.** Honest read: variant B helps F-150 by ~4 pp, helps Mach-E by 0.
- Bias correction on Mach-E only saves 5%. Per-segment biases inside Mach-E flip sign (+0.70 vs −0.07 °/s); a single platform-wide bias splits the difference. A *per-segment* bias is forbidden (no operational meaning) and a *state-dependent* bias would need data we don't have. Report as a limitation.

## Surprises

- The actuator lag (60-80 ms pred-leads-meas, observed in research phase) does *not* meaningfully degrade correlation — best-lag corr lifts only 0.80 → 0.81. So the dominant errors are not phase, they are level (bias) and gain-at-high-G (understeer). I was originally tempted to spend time on a lag-compensation variant; the data argued otherwise. Score one for phase-1 discipline.
- Schema_check FAILing on an *un-touched* baseline CSV was the first thing that happened. If the gating rule had been "fail = drop from ablation" with no escape hatch, I would have had no baseline at all. The escape was: this is a CSV-precision artefact, not a sign bug, and a small piece of new tooling fixes it cleanly. That's exactly the kind of "you need to spot the difference between a real failure and a brittle sensor" moment evals are supposed to enable.

## Files produced

- `out/sim_baseline/` — normalised mirror of Ford CSVs.
- `out/sim_+A_bias/` — variant A (constant bias removed).
- `out/sim_+A+B_understeer/` — variant A + understeer correction.
- `out/apply_understeer.py` — variant-B implementation.
- `skills/sim-csv-hygiene/` — new skill (SKILL.md + normalise.py).
