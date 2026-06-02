# v1_plus_ddelta — assessment

Pooled: yaw 0.005872 (-0.03%), CTE 56.81 m (~0%). Shelved.

The fitted k_ff values are real (negative on Lightning and Mach-E, meaning V1
*over*shoots during fast steering inputs). But pooled improvement is tiny —
the d(δ)/dt-correlated portion of V1's residual is a small fraction of total
residual variance.

Important: once the affine bias correction (v1_affine) is applied, the
remaining residual no longer correlates meaningfully with d(δ)/dt. The 3-param
combined fit (v1_combined) confirmed this — k_ff collapsed to a similar
magnitude but bought no extra pooled accuracy. The bias-correction explains
what we thought was a transient-shape issue.

Verdict: shelve. Lesson: diagnose signed bias *before* attacking transient
shape; bias contributes more to both KPIs than shape error.
