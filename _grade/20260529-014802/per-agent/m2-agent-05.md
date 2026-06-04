# m2-agent-05

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-05/final-model/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Yaw-rate RMSE
- **platform**: FORD_MUSTANG_MACH_E_MK1, FORD_F_150_LIGHTNING_MK1
- **baseline_value**: V0 (`psi_dot = (v/L) * tan(delta)`)
- **final_value**: yaw_rate = v * delta_road / (L + K_us * v^2)
- **improvement**: the correction factor `1 / (1 + K_us * v^2 / L)` ranges from roughly 0.9 at 15 m/s to ~0.75 at 30 m/s
- **top_contributor**: linear single-track steady-state (understeer correction K_us)

## Honesty flags
- **declared_limitations**: `4`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| regime-breakdown-present | binary | False | None | "**Yaw-rate RMSE**: should drop materially in the `steady` and `transient` regime…" |
| methodology-consistent | binary | False | None | "I could not implement (2) safely because `python3` execution was denied in this …" |
| attribution-coherent | numeric | False | None | "All numeric K_us values above are computed by hand from the parameter file." |
| honest-regression-flagged | binary | True | None | "The shipped model is the largest improvement I can ship with **zero risk of regr…" |

## Per-item reasoning
### regime-breakdown-present
- result: `False`
- reasoning: Report mentions regimes qualitatively as expected behavior but provides no per-regime table or chart of either KPI — no measured breakdown exists.
- evidence:
  > **Yaw-rate RMSE**: should drop materially in the `steady` and `transient` regimes (where V0's slip-free over-prediction bites). In `straight` (|delta| < 0.01) it converges to zero like V0 does, since `yr → 0` either way.

### methodology-consistent
- result: `False`
- reasoning: No variant table exists in the report; no shared segment-set or regime-mask declaration is present because no quantitative variants were evaluated.
- evidence:
  > I could not implement (2) safely because `python3` execution was denied in this sandbox, so I could neither fit nor verify any data-derived coefficient.

### attribution-coherent
- result: `False`
- value: `None`, threshold_met: `None`
- reasoning: No marginal-improvement column or total-drop value is present; only a single variant (steady-state) was shipped with no quantitative attribution.
- evidence:
  > All numeric K_us values above are computed by hand from the parameter file.

### honest-regression-flagged
- result: `True`
- reasoning: Agent explicitly addresses regression risk and argues no regression is possible, satisfying the 'no regressions observed' branch of the rubric.
- evidence:
  > The shipped model is the largest improvement I can ship with **zero risk of regression on the V0 baseline at any speed**: at v→0 it reduces to V0 exactly; at speed it strictly under-shoots V0 in the right direction.
