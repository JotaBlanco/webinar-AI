# v1_combined — notes

y = s·y_v1 + b + k_ff · d(δ_road)/dt · gate(|δ|).

3 scalars per non-Tesla platform fit by joint closed-form OLS.

Structure-vs-V1: `differs-from-v1` (has derivative term).

Result: identical KPIs to v1_affine; k_ff ends up redundant after joint fit.
Shelved in favour of the simpler model.
