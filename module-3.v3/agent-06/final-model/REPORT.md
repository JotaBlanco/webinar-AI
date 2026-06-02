# REPORT — agent-06 final-model (residual-learner)

See `../REPORT.md` for the full report.

**Shipped:** V1 + per-platform ridge linear regression on V1's residual using 7 allowlist features `[yr_V1, |yr_V1|, v, v·yr_V1, dδ/dt, δ, 1]`, λ=30.

**Pooled dev (sim/segments):** yaw 0.005770 rad/s (−1.8% vs V1), CTE 53.78 m (−5.3% vs V1).

Per-platform: Lightning 0.00557/63.4; Mach-E 0.00852/92.1 (CTE drift −22 m → −8.9 m); IONIQ-5 0.00750/65.5 (CTE drift −11.6 m → +1.9 m); Tesla V0 passthrough.
