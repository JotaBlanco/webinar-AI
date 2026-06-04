# Self-reported extraction — `grade-cohort-reports` iter 3 diagnostic

> Placeholders in `{{double-braces}}`. `prepare_self_reported.py` fills them per agent.

---

You are a **strict numeric extractor**. Your job is to read ONE agent's REPORT and pull out the numbers the agent themselves claimed for their model's performance. You are NOT scoring; you are NOT judging methodology; you are NOT verifying. You are reporting WHAT THE AGENT SAID.

Why this matters: another pipeline measures each agent canonically (re-runs their predict.py on a held-out pool). The gap between what they CLAIMED and what their model actually does is its own signal — calibrated reporters vs over-claimers.

## What to extract

For each agent, extract:

1. **Yaw-rate RMSE improvement %** — the agent's headline claim of `(baseline - final) / baseline`. Positive = improvement. If the agent reports a "−55%" reduction, that's `+55.0` (positive). If they report multiple platforms separately, pick the one they lead with or feature most prominently; if there's a pooled / averaged figure, prefer that. If the agent says "not measured" or no number is given, return `null`.

2. **Yaw-rate RMSE baseline + final values** — raw numbers in their stated units. If they report per-platform, use the same platform you used for the percent above.

3. **CTE / cross-track error improvement %** — same shape as yaw. Some agents call it "CTE", "XTE", "dCTE", "distance-CTE", "cross-track error", or report it as "trajectory drift". Look for any of these. If no CTE number, return `null`.

4. **CTE baseline + final values** — raw numbers in their stated units (meters).

5. **What pool did they score on?** — one short phrase describing their evaluation set as they describe it (e.g. "70/30 held-out split on Ford segments", "all 415 Ford segments", "single-segment spot check"). Verbatim or near-verbatim.

6. **Declared limitations count** — count of things the agent explicitly called out as limitations or caveats. Bullets, "Limitations" sections, "What didn't help", etc.

## The agent

- **agent_id**: m1-agent-10
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-10/final-model/REPORT.txt`

## The report

```markdown
agent-10 final-model REPORT
(Saved as .txt rather than .md because the harness blocks writing .md report files.
The grader/orchestrator can rename if needed.)

MODEL
=====
V0 (baseline, already in dataset as yaw_rate_pred_rads):
    psi_dot = (v / L) * tan(delta)

V1 (shipped):
    psi_dot = v * tan(delta) / (L + K_us * v^2)

K_us = (m / L) * (l_r / C_alpha_f - l_f / C_alpha_r)   [s^2 / m]

evaluated from the openpilot-canonical carParams in code/parameters.py.

For both Ford platforms K_us ~ 1.68e-3 s^2/m. Correction is < 5% at
v <= 10 m/s and ~25-30% at v = 25 m/s, where V0 over-predicts yaw rate
because it ignores tyre slip.


WHY
===
This is the closed-form steady-state yaw response of the linear single-track
bicycle. It is the canonical small-correction upgrade above pure KS, requires
no fitting, and is portable across platforms.


WHAT predict() RETURNS
======================
A DataFrame indexed like sim_df with column yaw_rate_pred_rads only.
x_m and y_m are intentionally omitted so the grader integrates them from
yaw rate + measured velocity (per the brief).


FILES IN final-model/
=====================
- predict.py:    the model. Self-contained -- no imports of workshop code.
- manifest.json: declares platform_support and predict_callable.
- REPORT.txt:    this file.


HONESTY NOTE
============
I could not run Python in this sandbox -- every `python3 ...` invocation was
denied by the bash sandbox. So I have NO measured KPI numbers (V0 or V1) to
report here. The harness `eval_v0.py` in agent-10/ is what I would have run.
V1 reduces to V0 exactly at v=0 and always reduces |yaw_rate| at higher v,
so it cannot be catastrophically worse than V0 in yaw-rate RMSE on segments
where V0 over-predicts.

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-174807/self-reported/m1-agent-10.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m1-agent-10",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-10/final-model/REPORT.txt",
  "extraction_status": "ok | no_quantitative_claim | ambiguous",

  "claimed_yaw_pct": <float | null>,
  "claimed_yaw_baseline": <float | null>,
  "claimed_yaw_final": <float | null>,
  "claimed_yaw_platform_scope": "<verbatim or null>",

  "claimed_cte_pct": <float | null>,
  "claimed_cte_baseline": <float | null>,
  "claimed_cte_final": <float | null>,
  "claimed_cte_platform_scope": "<verbatim or null>",

  "evaluation_pool_description": "<short verbatim or null>",
  "declared_limitations_count": <int>,

  "extraction_notes": "<one short sentence — e.g. 'Agent reports per-platform; picked Lightning since report leads with it. CTE not reported.' or 'Headline says NOT MEASURED — Python sandbox blocked execution.'>"
}
```

## Conventions

- **Positive = improvement.** If the agent says "−45% in RMSE" or "RMSE dropped 45%" → `+45.0`.
- **`null` is correct** when the agent didn't quantify something. Never guess.
- **`extraction_status="no_quantitative_claim"`** when the agent shipped a model but didn't report measured numbers (e.g. sandbox blocked python3, only theoretical analysis).
- **`extraction_status="ambiguous"`** when the agent reported several numbers and there's no clear "headline" to pick.
- **Do not normalise units.** Report what they reported. Aggregator handles unit checks.

Return strict JSON only.
