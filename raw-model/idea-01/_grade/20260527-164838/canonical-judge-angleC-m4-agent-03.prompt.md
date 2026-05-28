# Canonical-eval judge prompt template — `grade-cohort-reports`

> Placeholders in `{{double-braces}}`. `prepare_canonical.py` fills them per agent.

---

You are a **canonical-evaluation judge**. Your job is to take ONE agent's reported "favourite" yaw-rate model, reconstruct it, run it against a fixed canonical evaluation set, and report the resulting RMSE — **replacing the agent's self-reported headline with a comparable, like-for-like number**.

We do this because every agent picked their own baseline, their own segment subset, and their own metric definition — so their headline % improvements are not comparable. Re-running each model against the same dataset under the same conditions is the only honest cross-agent comparison.

## The agent

- agent_id: **angleC-m4-agent-03**
- agent folder: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-03`
- report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-03/REPORT.md`

## The canonical eval setup (verbatim from the idea's `.canonical.yaml`)

```yaml
idea_id: idea-01-lateral-attribution
description: |
  Canonical evaluation spec for idea-01. Each agent's "favourite" yaw-rate model is
  reconstructed from their report + scripts + outputs, then run against this fixed
  dataset under fixed conditions. The resulting RMSE replaces the agent's
  self-reported headline for cross-agent comparison.

eval_set:
  description: All Ford sim segments under data/sim/segments/FORD_*/...
  segment_globs:
    - data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv
    - data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv
  sample_filter: "v_mps > 2.0"
  truth_channel: yaw_rate_meas_rads

baseline:
  name: V0 (unmodified KS model)
  source: |
    The sim.csv files ALREADY contain the V0 prediction in the column
    `yaw_rate_pred_rads`. This is the output of `simulate_ks(clamp_v_to_measured=True)`
    with the unmodified model — i.e. V0 by construction.
  computed_once: true   # prepare_canonical.py computes this once across all canonical segments and caches it

metric:
  name: pooled-sample yaw-rate RMSE
  unit: rad/s
  formula: sqrt(mean((agent_pred - truth)**2)) over all qualifying samples
  improvement_formula: (baseline_rmse - agent_rmse) / baseline_rmse * 100  # positive = better

reconstruction_priority:
  - Read fitted coefficients / parameters from agent's out/*.json or out/*.csv if present; combine with the prediction equation described in the REPORT
  - Import and call agent's predict function from tools/*.py
  - Re-run the agent's training script in their folder (slow; only if other options fail)

failure_action: |
  If reconstruction is infeasible — agent didn't save coefficients, code crashes,
  model is described too vaguely to reproduce, or platform-restricted to non-Ford —
  return status="failed" with a one-sentence reason. Do not fabricate numbers.

leakage_note: |
  Many agents trained on the same Ford segments we score against. We accept this
  leakage: the "model" each agent shipped is their fitted parameter set, and we
  measure how well that parameter set predicts the full Ford dataset. Linear-fit
  generalisation is good and the cross-agent comparison stays valid because every
  agent is scored on the same data with the same baseline.
```

**Precomputed V0 baseline (cached from the canonical eval set — sanity-check yours against this):**

```json
{
  "rmse_rad_per_s": 0.014740020892723483,
  "n_segments": 545,
  "n_samples_after_filter": 1364925,
  "truth_channel": "yaw_rate_meas_rads",
  "sample_filter": "v_mps > 2.0",
  "globs": [
    "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv"
  ],
  "computed_at": "2026-05-27T16:48:41"
}
```

## What you must do

1. **Identify the agent's "favourite" / "final" model.** Read their `REPORT.md`, scripts under `tools/`, and outputs under `out/`. The variant they call best/final/V4/etc. If they report multiple variants, pick the one they label as best in their own words. Quote the line where they declare it.

2. **Reconstruct a callable that produces yaw-rate predictions in rad/s for any sim.csv segment**, using the priority list above:
   1. Read fitted parameters from `out/*.json` or `out/*.csv` and reconstruct the prediction equation from the REPORT's description.
   2. Import and call a predict function from `tools/*.py`.
   3. Re-run the agent's training script in their folder (slow; only if 1/2 fail).

   If none work — agent didn't save coefficients, code crashes, model is described too vaguely to reproduce, or the model is restricted to a non-Ford platform — STOP and report status=`failed` with a one-sentence reason. **Do NOT fabricate numbers.**

3. **Apply to ALL canonical segments.** Glob the segment paths from the YAML's `segment_globs`. For each segment, load `sim.csv`, apply your reconstructed predict to produce a per-row yaw-rate prediction, and store the predictions.

4. **Compute metrics.** Pool all samples where the YAML's `sample_filter` holds. Compute:
   - `baseline_rmse_recomputed` = RMSE between sim.csv's existing `yaw_rate_pred_rads` column and the YAML's `truth_channel`. Sanity-check: this should match the precomputed `baseline_rmse` above to within 1e-6. If it doesn't, flag in `notes`.
   - `agent_rmse` = RMSE between YOUR reconstructed predictions and the truth.
   - `improvement_pct` = `(baseline_rmse - agent_rmse) / baseline_rmse * 100`. Positive = better.

5. **Write strict JSON to `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/_grade/20260527-164838/canonical/angleC-m4-agent-03.json`.** No prose around it, no markdown fence.

```json
{
  "agent_id": "angleC-m4-agent-03",
  "status": "ok",
  "reason": null,
  "reconstruction_method": "json-coeffs | imported-function | re-ran-script | other",
  "reconstruction_summary": "<one sentence — which variant of the agent's model you re-ran and how you got the parameters>",
  "n_segments": <int>,
  "n_samples_after_filter": <int>,
  "baseline_rmse": <float — rad/s, the canonical V0>,
  "baseline_rmse_recomputed": <float — your sanity-check recomputation>,
  "agent_rmse": <float — rad/s>,
  "improvement_pct": <float — positive = better>,
  "notes": "<anything noteworthy: 'agent's script seeded RNG, results reproduce exactly', 'agent's coefficients are platform-specific so pooling across Ford platforms loses fidelity', etc.>"
}
```

If reconstruction fails, write:

```json
{
  "agent_id": "angleC-m4-agent-03",
  "status": "failed",
  "reason": "<one-sentence reason — e.g. 'agent's coefficients not saved and training script requires raw rlog access not available'>",
  "reconstruction_method": "failed",
  "reconstruction_summary": null,
  "n_segments": null,
  "n_samples_after_filter": null,
  "baseline_rmse": <float — the canonical V0, copy from above>,
  "baseline_rmse_recomputed": null,
  "agent_rmse": null,
  "improvement_pct": null,
  "notes": "<context, including what you tried>"
}
```

After writing, return one short sentence: `Canonical eval for angleC-m4-agent-03: status=<ok|failed>`. Nothing else.

DO NOT:
- Skip the per-segment loop and sample only a subset for speed.
- Fabricate numbers if reconstruction fails.
- Use any segments outside the canonical set.
- Modify files under `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-03/code/` or `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-03/data/` (these are symlinks to shared, read-only resources).
- Modify ANY file under `data/sim/` (this is the canonical V0 baseline — read-only by contract).
- Persist bulk per-row predictions to disk. Stream through segments and accumulate RMSE in memory; only the JSON output is needed.

Time budget: ~15 minutes. If your reconstruction approach has been running for &gt;10 minutes with no end in sight, stop, capture what you can, and report `status="failed"` with the reason being "exceeded time budget at <step>".
