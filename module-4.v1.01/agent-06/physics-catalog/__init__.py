"""physics-catalog — pre-built physics models, beyond V1's kinematic bicycle.

Each subdir is one model. Same operating contract as V1: a `predict(sim_df,
platform)` function reading the 8-column allowlist, returning a DataFrame
with a `yaw_rate_pred_rads` column.

Models (in increasing structural complexity):

- `dst_lin`     — Linear-tire dynamic single-track (rung 1).
- `dst_nl`      — Pacejka-lite saturating tire on top of dst_lin (rung 2).
- `dst_regime`  — Kinematic V1 below |v·ψ̇| threshold, dst_lin above (rung 1, gated).
- `dst_relax`   — dst_lin + tire-relaxation length (rung 2, physics-justified lag).
- `dst_load`    — dst_lin + longitudinal-accel load transfer per axle (rung 3).

Workflow:

  cp -r physics-catalog/<model_name> models/<your-name>
  python -m physics-catalog.<model_name>.fit  # refit on your dev split
  python -m skills.iterate.iterate models/<your-name>

See README.md for the full table and physics-menu.md for residual-character mapping.
"""
