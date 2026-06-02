# v1_plus_delta0 — notes

V1 with per-segment δ₀ enabled for ALL non-Tesla platforms (V1 only enables
it for Mach-E and IONIQ-5). Otherwise identical: KS + understeer + 1st-order
lag.

State: V1's lag state. Integrator: V1's. Coeffs: V1's (g, L_eff, K_us, τ).

Expected residual character: tighter steering-zero offset → less yaw bias on
Lightning. Reality: per-segment median is noisier than Lightning's fixed
δ₀=0.00133, so it injected +0.005 rad/s of yaw bias.

Structure: refines-v1 (config tweak).
