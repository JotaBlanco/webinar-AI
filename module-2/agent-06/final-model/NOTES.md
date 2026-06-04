# V2 bundle notes

Substantive report goes at `../REPORT.md` (written by orchestrator from final-response text, since the sub-agent harness blocks `(report|findings|summary|analysis).*\.md`).

Model: per-platform refit of `yaw_pred = v*(delta + tau*d_delta_dt)/(L + Kus*v^2) + bias`. Tesla is V0 passthrough. Coefficients in `coeffs.json`.
