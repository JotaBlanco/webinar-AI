# Assessment — dynamic-single-track

## Verdict

**Drafted, not implemented.** The formulation is in notes.md (linear bicycle,
`(a, C_f, C_r)` per platform). The residual-learner candidate (v1-plus-residual)
ate the time budget that would have gone into the nonlinear identification
loop here.

Honest negative: would expect this model to capture more of Mach-E's
transient regime than the residual learner does, because it has the
cornering-stiffness dynamics by construction rather than as a regression
target. If a future agent picks this up, start with `(a, b) = (L_eff/2,
L_eff/2)` and `(C_f, C_r) ≈ 80 kN/rad` per axle — those are within the
plausible range for the three platforms.

Registered `structure: differs-from-v1`, `status: drafting`.
