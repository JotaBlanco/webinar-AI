# Final-model bundle — agent-04

Shipped model: V1 baseline (kinematic single-track + understeer + first-order yaw lag + per-segment delta0).

Dev pooled: yaw RMSE = 0.005430 rad/s, CTE RMSE = 52.22 m.

Per-platform (dev):
- F150  Lightning: yaw 0.007541, CTE 93.77
- Mach-E:         yaw 0.008271, CTE 63.65
- Ioniq 5:        yaw 0.006497, CTE 67.17
- Tesla:          yaw 0.0, CTE 0.0 (passthrough — no truth channel)

Rung climb attempts logged in MODELS.md / EXPERIMENTS.md / TREE.json:
- M1 linear-dynamic-st (rung 1): shelved — L-BFGS-B fit did not converge inside wall-clock budget under heavy parallel-cohort CPU contention.
- M4 relaxation-length (rung orthogonal): kept — sigma grid-fit per platform (F150=0.3 m, Mach-E=0.5 m, Ioniq=0.3 m) gave pooled yaw 0.005636, CTE 52.15. Near-tie with V1, did not promote.

The full agent report is at the module-root REPORT.md, written by the orchestrator from the final-response text.
