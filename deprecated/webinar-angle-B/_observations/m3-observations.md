# M3 — observations

## Run summary
- Duration: ~4.9 min (295s)
- Total tokens: ~58.7k — *more* than M1/M2
- Tool uses: 23 — *more* than M1/M2
- REPORT.md: written
- Isolation: respected
- **Skills loaded fully**: both. Order: `sim-real-runtime` then `vehicle-dynamics-rlog`.

## What worked
- **Best numerical results so far.** On the segments that actually have lateral content (F-150 seg-9, |δ|_max ≈ 25°), ST+bias gives **−59%**. Aggregate: Mach-E **−82%**, F-150 **−68%**.
- Implemented BOTH steady-state ST (V2) AND full dynamic ST with β state (V3) — that's the *transient* lag the SKILL.md flagged.
- Created `ablation.py`, `ablation_dynamic.py`, and an `ablation_results.csv` — reproducible artifacts.
- Distinguished aggregate vs per-segment RMSE, surfacing that "3 of 4 segments are straights" — the kind of nuance M1 and M2 didn't reach.

## What slowed the agent down
1. **Three of four segments are essentially straights** (|δ_road| < 0.6°). Aggregate RMSE was dominated by sensor bias, not model lie. Agent had to write a second per-segment script to find the segment that exercises the lateral model. *Same data problem M1 + M2 hit, but M3 caught it explicitly.*
2. **`TodoWrite` system reminders were noise** for a 25-min linear task with no branching. (Orchestrator note: the harness keeps suggesting it; the agent rightly ignored.)
3. **REPORT.md write was intercepted** by the subagent harness — same as M2 — fell back to Bash heredoc. Reproducible friction.
4. **No `st_model.py` in `code/`** — agent had to inline ST in the ablation script rather than properly extending the model module.

## My observations as orchestrator

**The skills paid off.** Compare:
- M1 (no skills): proposed ST but implemented it as a *closed-form correction* (`ψ̇ = vδ/(L + K_us·v²)`). Best F-150 result: −47%.
- M2 (CLAUDE dump): same closed-form ST. Best F-150 result: −63% (with stacking of bias + steer cal + understeer + lag).
- M3 (with skills): implemented BOTH steady-state ST AND full dynamic ST with β state. Best F-150 result: −68% aggregate (−59% on the lateral-rich segment).

The `vehicle-dynamics-rlog/SKILL.md` explicitly named "ST adds tyre cornering stiffness... and the slip angle. The states add β (sideslip angle) and ψ̇ becomes a true integrated state". M3's agent then implemented exactly that — full β-state dynamic ST — where M1/M2 stopped at steady-state. **This is the workshop's core claim landing empirically**: well-positioned domain knowledge unlocks a deeper engineering response.

**Token cost is monotonic upward (M1 → M2 → M3).** 50k → 48k → 58k. The skills add cost because they get *loaded* (the agent followed the metadata pointer and read the body). But the *output quality* is much higher. This is the right trade-off — exactly what NC-12 (progressive disclosure) promises: pay tokens *for* the right thing, *when* it's needed.

**Per-segment analysis was the unlock.** The skill's "What the residual is telling you" section primed the agent to think about regime decomposition. M1 and M2 reported one aggregate number; M3 surfaced the segment heterogeneity.

## Same problems all 3 modules hit (env-level, not substrate-level)
- Only 2 segments per platform.
- No CAN-decode deps installed.
- The Write-tool/subagent-deliverable friction.

## Hypothesis for M4
M4's RPI scaffolding should force the agent to:
- **Research phase**: explicitly catalogue the segment regime distribution upfront (so it doesn't get burned by 3/4 being straights mid-implementation).
- **Plan phase**: select WHICH ST formulation (steady-state vs dynamic) BEFORE implementing, with a stated success criterion.
- **Implement phase**: cleaner execution because the plan is locked.

Cost: more tokens (3 phases). Benefit: better organisation of the same insight M3 reached, potentially with the additional "found the data limitation upfront" win.

Risk: in a single-agent simulation of 3 fresh windows (which is what we're doing), the discipline is more performative than real — context doesn't actually clear between phases. We'll see whether the artifact-handoff discipline alone provides value.
