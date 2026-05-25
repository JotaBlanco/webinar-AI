# M4 — observations

## Run summary
- Duration: ~8.6 min (517s) — *longest by far* (~2× M3)
- Total tokens: ~75.9k — *highest of all 4*
- Tool uses: 33 — *highest of all 4*
- All four RPI artifacts written: `tasks/research.md`, `tasks/plan.md`, `tasks/implement-notes.md`, `REPORT.md`
- Isolation: respected
- Skills loaded fully: both, in phase 1.

## Numerical result
- Mach-E: 0.505 → **0.121** (−76%). Best Mach-E result of all 4.
- F-150: 1.105 → **0.544** (−51%).

The F-150 result is **WORSE than M3's** (−51% vs −68% aggregate / −59% on lateral-rich segment). The Mach-E result is comparable to M3's −82%.

## Why M4 didn't beat M3 numerically

The agent **explicitly deferred H2 (full dynamic ST with β state) in `plan.md` because it was "too risky inside time budget" and picked H3 (steady-state understeer correction)** instead. M3, with no plan-locking discipline, just *took the swing* and implemented dynamic ST — which is what closed the F-150 gap.

> Quoting M4's plan: *"H2 (full ST) would be the proper fix but is ~120 LOC + integrator stability risk inside a 30-min budget. H3 captures the steady-state portion of ST's correction with a single closed-form factor."*

**This is the most interesting finding of the experiment.** RPI discipline made the agent **conservative**. It traded a higher-variance, higher-upside approach (M3's dynamic ST that ate ~5 extra tool uses) for a lower-variance, lower-upside approach (closed-form understeer correction). On this short-budget task with cheap iteration, the bet was wrong; on a real production brownfield task where a failed ST integration costs hours, the bet would have been right.

## What the agent itself said about RPI discipline

> "Helped, net positive. Writing research.md forced me to actually inspect per-segment biases (which revealed Mach-E was straight-line driving and the residual was sensor bias) instead of jumping to 'let's write ST'. Locking plan.md then prevented mid-implementation scope creep into H2. Cost was ~3 min of writing; benefit was avoiding a likely failed ST integration in the time budget. The 'treat phase-2 as fresh' framing felt artificial inside one session but the discipline of only working off the artifacts is what kept the scope tight."

So the agent *experienced* the discipline as helpful — but on *this* task the help was guard-railing into a more conservative solution. The agent and the orchestrator can disagree on whether that trade-off was right; both are correct in their frames.

## What the artifacts revealed that earlier modules missed

The M4 `research.md` is the **best diagnostic write-up of any of the four**. In particular:
- It cleanly separated *per-segment* bias from *per-platform* bias (M1 conflated; M2 partly addressed via in-sample stacking; M3 caught it via per-segment script).
- It computed `psi_dot_meas/psi_dot_pred = 0.851` on F-150 cornering samples — the textbook "tyres give 15%" gap, named explicitly.
- It bucketed F-150 residual by speed bin AND by |a_y| bin and showed the monotonic growth (1.05 / 1.42 / 2.16 °/s for low / mid / high |a_y|).

None of M1-M3 produced an analysis this organised. The forced "write to a fresh engineer" framing paid off in *clarity of thought*, even though it cost in tokens and ultimately led to a more conservative pick.

## Cost/value comparison

| Module | Tokens | Tool uses | Duration | F-150 best | Mach-E best |
|---|--:|--:|--:|--:|--:|
| M1 | 50k | 18 | 4.4 min | −47% | −1% |
| M2 | 48k | 14 | 3.9 min | −63% | −22% |
| M3 | 59k | 23 | 4.9 min | **−68%** | **−82%** |
| M4 | 76k | 33 | 8.6 min | −51% | −76% |

M4 paid a ~50% premium in time/tokens over M3 and got a *worse* numerical headline. But M4's *analytical artifacts* (research.md, plan.md, implement-notes.md) are reproducible, hand-offable, reviewable. M3's ablation scripts work but a different engineer arriving cold could not pick up M3's reasoning trail; they could pick up M4's.

This is the workshop's most honest finding: **the RPI loop's value is asymmetric — it underperforms on short cheap-iteration tasks and overperforms when the artifact handoff is the actual deliverable**. The workshop's audience needs to hear this without it being smoothed into a "RPI is always better" claim.

## Same problems all 4 modules hit
- Only 2 segments per platform.
- No CAN-decode deps installed.
- Write tool / subagent harness friction on REPORT.md (M2, M3, M4 all had this; M1 may have hit it but didn't mention it).
