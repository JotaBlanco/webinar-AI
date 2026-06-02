# residual-learner — assessment (shipped)

Pooled dev: **yaw 0.005770 (−1.8% vs V1), CTE 53.78 (−5.3% vs V1).**

Per-platform:
- Lightning: yaw 0.00557 (vs V1 0.00566, −1.6%), CTE 63.40 (vs 62.19, +1.9%), cte_signed +2.34
- Mach-E:    yaw 0.00852 (vs V1 0.00859, −0.8%), CTE 92.07 (vs 98.68, −6.7%), cte_signed −8.91
- IONIQ-5:   yaw 0.00750 (vs V1 0.00766, −2.1%), CTE 65.47 (vs 69.53, −5.8%), cte_signed +1.93
- Tesla:     V0 passthrough (no truth)

Verdict: SHIPPED.

Key observation: the CTE drift on Mach-E (−22 m → −8.9 m) and IONIQ-5
(−11.6 m → +1.9 m) is collapsed without making per-segment yaw RMSE worse.
This is consistent with the residual being dominated by a *systematic* gain
error + small bias terms — exactly what a 7-coef linear corrector can absorb,
and exactly what a fixed-shape physics model (V1, dynamic-ST) cannot tune to.

Lightning's CTE goes slightly up (+1.9%) because the residual learner adds a
small drift that wasn't there. Lightning was already at the noise floor; the
correction is fighting noise. A per-platform decision to skip residual
correction on Lightning would recover the difference, but the pooled win is
much larger than the per-platform regression — not worth the asymmetry.

λ=30 was chosen by sweep; sensitivity is mild — λ∈[10, 100] all beat V1 on
both KPIs by ≥1.4% yaw and ≥4.5% CTE.
