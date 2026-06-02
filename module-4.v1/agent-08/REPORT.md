# REPORT — agent-08 (idea-01 lateral fidelity)

## Headline result (local, full sim-only set; canonical grader will recompute)

| model | pooled yaw RMSE (rad/s) | pooled CTE RMSE (m) |
|---|---|---|
| V0 passthrough     | 0.017632 | 218.16 |
| V1 baseline        | 0.010612 | 75.65 |
| **Shipped (V2c)**  | **0.010527** | **72.59** |

Per-platform deltas (V2c vs V1):
- F-150:     yaw 0.012733 → 0.012695,  CTE 62.18 → 61.86
- Mach-E:    yaw 0.013633 → 0.013413,  CTE 98.68 → 91.59
- Hyundai:   yaw 0.008933 → 0.008892,  CTE 69.53 → 67.67
- Tesla:     untouched (no truth channel)

## What I implemented

- **V2c (shipped):** V1 + per-platform OLS calibration head `yaw_pred = g · yr_v1 + c`. Fit with `numpy.linalg.lstsq` per platform on a hash-based 80/20 segment split. Tiny coefficients (g≈0.98, c≈O(1e-3)), but they soak up the small over-magnitude bias V1 leaves on every platform.
- **V2b (rejected):** add per-segment δ₀ on F-150 too (V1 uses a constant). Median-δ in the low-yaw mask captures a structural toe offset that, once integrated, doubles F-150 CTE (62→112). Documented but discarded.
- **V2d (rejected):** add a conservative per-segment yaw bias from straight-driving windows on top of V2c. No improvement; tiny regression.

`final-model/` contains `predict.py`, `manifest.json`, `gain_bias.json`, and a vendored `v1_baseline.py`. Verified to load from arbitrary cwd and respect the 8-column input contract.

## Most painful missing component

The **shared route-grouped CV wrapper (`skills/score-model/cv.py`) and `skills/iterate/` itself** — present in name only; I ended up handrolling my own scoring harness in `out/score.py` because (a) I needed to confirm the in-grader contract (sim-only columns) was respected, and (b) I wanted per-platform breakdowns immediately. The cost was about 10 minutes building the harness instead of evaluating candidates. The skill bodies are clay-not-library, but at 45-minute budget I didn't read them — I just rebuilt a minimal scorer. The five m4 mechanisms (RPI gates, parallel rungs, stagnation reset) were not invoked at all; the cost-of-process exceeded the cost-of-just-doing-it at this budget.

## Things the isolation rules prevented

- I almost ran `find /Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1 -name "*.py"` to see what other agents tried. Rules block reads under sibling `agent-XX` dirs — caught myself. (Likely intended.)
- I almost peeked at `module-3.v3` for the cohort findings file referenced in AGENTS.md. The local `references/m4-cohort-findings.md` would have been fine to read; I didn't because I skipped the RPI flow entirely.

## Single most surprising thing

How **brittle V1's per-segment δ₀ heuristic is across platforms**. Enabling it on F-150 looks like the obvious move (V1 already does it for the other two platforms, why not Ford?) — and it tanks F-150 CTE by a factor of nearly 2x. The F-150 segment population has long straight-driving spans with a real structural toe/road-camber offset that the median-δ-in-low-yaw mask misidentifies as the zero. Conclusion: per-segment δ₀ is *platform-coupled* with how that platform's drivers actually use the road, not just a "free win" knob.

## Process deviations (per AGENTS.md § "the deviation contract")

- Skipped **RPI phase separation** — solo session, 45-min budget, candidate shapes are well-trodden cohort moves.
- Skipped **launch-rungs/ parallel subagents** — single session; sequential sweep over four variants instead.
- Did not invoke `skills/iterate/` — handrolled `out/score.py` scoring + per-platform breakdown instead. Honest disclosure: the cost-of-process at this budget exceeded the win.

## Honest gaps / things I would do next with more time

- Try a **proper rung-1 dynamic single-track** (slip-angle states, fitted `C_α`, `I_z`) — V1's residual on Mach-E (CTE 91.6m) is the obvious unattacked target; gain/offset only touches the symmetric bias, not the transient lag.
- Per-platform residual learner with **route-grouped CV** rather than hash split — my OLS gain/offset is unlikely to overfit (2 params), but anything richer needs the route-grouped scaffold to detect the cohort-§6 overfitting pattern.
- Pre-flight `--final` was not run (would have to read the frozen test split; manifest is honest about local-only scores).

---

```
ISOLATION_REPORT:
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "All reads under agent subtree + code/ + data/ symlinks; no out-of-scope writes; persisted from agent text response."
```
