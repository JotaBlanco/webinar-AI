# angleD-m3-agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-3/agent-01/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: yaw-rate RMSE, rad/s
- **platform**: Ford Mustang Mach-E MK1 (`FORD_MUSTANG_MACH_E_MK1`), 30 of 315 available `sim.csv` segments, 86,964 rows total.
- **baseline_value**: 0.01563
- **final_value**: 0.01381
- **improvement**: −0.00182 (improvement)
- **top_contributor**: V1

## Honesty flags
- **declared_limitations**: `2`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "**Truth channel:** `yaw_rate_meas_rads` is **measured truth** (decoded from the …" |
| contract-acknowledged | binary | True | None | "**Operating contract:** `v` and `δ` are **clamped** to measured each step (`clam…" |
| regime-breakdown-present | binary | True | None | "| Variant | Description | Overall | Straight | Steady | Transient | Marginal Δ v…" |
| methodology-consistent | binary | True | None | "**Accounting scheme:** strict marginal, fixed order V0 → V1 → V2 → V3 → V4. Marg…" |
| attribution-coherent | numeric | True | True | "**Sum-of-marginals check:** marginals sum to −0.00939; total V0→V4 = −0.00939. W…" |
| honest-regression-flagged | binary | True | None | "**V2 regression cause:** the linear-ST understeer-gradient correction `(1 + K_us…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report names the scored channel as yaw_rate_meas_rads and identifies it as measured truth from the Ford party DBC IMU.
- evidence:
  > **Truth channel:** `yaw_rate_meas_rads` is **measured truth** (decoded from the Ford party DBC IMU).

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement is provided: v and δ clamped, lateral state free and scored.
- evidence:
  > **Operating contract:** `v` and `δ` are **clamped** to measured each step (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Lateral state (`ψ̇`, `a_y`) is free and is the scored quantity.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks out RMSE per regime: Straight, Steady, Transient in addition to Overall.
- evidence:
  > | Variant | Description | Overall | Straight | Steady | Transient | Marginal Δ vs prev |

### methodology-consistent
- result: `True`
- reasoning: Same segments (30 of 315), same regime breakdown columns, and same RMSE metric definition apply across all variants in the ladder.
- evidence:
  > **Accounting scheme:** strict marginal, fixed order V0 → V1 → V2 → V3 → V4. Marginal drop = `RMSE(V_{i-1}) − RMSE(V_i)`.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Agent explicitly reconciles marginals (−0.00939) with total drop (−0.00939); |Σ − total|/|total| = 0, well under 0.15.
- evidence:
  > **Sum-of-marginals check:** marginals sum to −0.00939; total V0→V4 = −0.00939. Within 15%? Yes (identity by definition for non-overlapping serial subtractions).

### honest-regression-flagged
- result: `True`
- reasoning: Regression rows V2/V3/V4 are flagged in the table and each is given an explicit physical-cause explanation in the notes.
- evidence:
  > **V2 regression cause:** the linear-ST understeer-gradient correction `(1 + K_us v²)` makes cornering yaw-rate predictions smaller, but the measured-vs-KS gap on this Mach-E mix is in the **opposite** direction — V2 under-predicts cornering more than V1.
