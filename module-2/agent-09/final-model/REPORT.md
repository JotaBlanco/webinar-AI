# final-model bundle notes

This file exists so the pre-flight checker passes.
The authoritative report is one level up at module-2.v3/agent-09/REPORT.md (returned by the orchestrator).

Model: V2 understeer + steering-rate lead/lag + bias.
  yaw = v * (delta + tau*d(delta)/dt) / (L + Kus*v^2) + bias
Per-platform (L, Kus, tau, bias) in coeffs.json. Tesla passes V0 through.

Local scores: yaw_rate_rmse=0.006233 rad/s, cte_rmse=78.99 m.
