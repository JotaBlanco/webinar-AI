# notes.md — m3-double-track-load-transfer

- rung: 3
- parent: m2-fiala-tire-st
- status: drafting

## What this differs from

- **m2-fiala-tire-st (parent):** M2 evaluates Fiala once per axle against
  the *static* axle normal load. M3 splits each axle into an inner and
  outer wheel, applies a quasi-static lateral-load-transfer formula
  (`ΔF_z = m_axle · a_y · h_cg / t_w`) to get per-wheel `F_z`, and
  evaluates Fiala twice per axle with half the axle stiffness on each
  wheel. The axle force is the sum. This makes inner-wheel saturation
  visible: at high `a_lat` the inner `F_z` clamps toward zero while the
  outer still has capacity — exactly the regime M2 misses and where the
  axle-averaged stiffness drops faster than the linear-tire view
  predicts.
- **v1 (kinematic single-track + understeer + first-order lag):** V1
  has no concept of `F_z` at all — a single `K_us` scalar absorbs every
  load-distribution effect into one constant. M3 makes the load
  distribution dynamic in `a_y`, which is what changes between a
  straight cruise and a sustained sweeper.
- **F150 ceiling as the target:** see `references/f150-yaw-ceiling.md`.
  90 cohort agents have hit a ~+21% pooled-yaw ceiling on F150
  specifically because V1's steady-state understeer cannot represent the
  truck's load-transfer-driven understeer growth at sustained `a_lat`.
  M3 is the physics targeted at that failure mode.

## What residual symptom this targets

F150 yaw RMSE on highway sweepers (`v > 25 m/s`, `|a_lat| ∈ [2, 5]`),
and the per-platform signed yaw-bias residual the cohort sees on heavy /
high-CG vehicles in sustained-`a_lat` regimes. Not expected to help
Mach-E (light, low CG); on Mach-E the load-transfer split is overkill
and may regress CTE while yaw barely moves.

## a_y proxy and stability

`a_y = ψ̇ · v` evaluated from the *current* state inside `_state_dot`.
RK4 stays well-behaved because `a_y` only enters through `F_z` (an
input to Fiala), not directly through the state-derivative algebra. If
chattering appears at very low μ on the limit, switch to the previous
step's ψ̇ as a predictor-corrector — see model.py's
`_run_dynamic`.

## Identifiability caveat

When inner-wheel `F_z` clamps to zero (steady cornering at the limit),
the axle force becomes a function of only the outer wheel's parameters.
In that regime μ_r and C_α_r on the unloaded side are not identifiable.
This is by design — the limit physics requires the inner wheel to go
slack — but fits may show `stuck_on_bound` on μ_r for Ioniq / Mach-E
where high-`a_lat` data is sparse.
