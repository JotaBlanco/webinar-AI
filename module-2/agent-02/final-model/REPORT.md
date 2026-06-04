# final-model bundle — V2 understeer + steering-rate lead

Per-platform linear understeer with a phase-lead term on steering.

  yaw_rate(t) = v(t) * delta_eff(t) / (L_eff + K_us * v(t)^2) + b
  delta_eff(t) = delta(t) + tau * d(delta)/dt

Coefficients live in `coeffs.json`. Tesla passes V0 through (the dataset's Tesla
truth IS the V0 KS output).

Full task discussion lives in the parent `REPORT.md` at the agent root.
