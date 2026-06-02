# affine-v1 — assessment

Pooled dev: yaw 0.005859 (vs V1 0.005874), CTE 54.98 (vs V1 56.81).

Per-platform:
- Lightning: yaw 0.00571, cte 61.90, cte_signed +1.00
- Mach-E: yaw 0.00853, cte 92.37, cte_signed −5.88
- IONIQ-5: yaw 0.00765, cte 68.37, cte_signed −7.33

Verdict: keep as benchmark. Confirms per-platform gain error is a real signal.
Subsumed by residual-learner (E03) which contains [yr_v1, 1] columns and more.
