# v1_plus_delta0 — assessment

Pooled: yaw 0.006012 (+2.3% vs V1), CTE 69.70 m (+22.7% vs V1). Shelved.

Failure mode: per-segment δ₀ median is a noisy estimator on Lightning, whose
true steering-zero is stable across segments. The fixed δ₀ in V1 was the
right call for Lightning. Mach-E and IONIQ-5 results basically unchanged.

Verdict: shelve. Lesson: V1's per-platform per-segment-vs-fixed δ₀ choice
already reflects calibration realities; don't override it without evidence.
