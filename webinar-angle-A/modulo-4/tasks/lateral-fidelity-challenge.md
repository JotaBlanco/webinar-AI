
# Lateral fidelity — quantify the contribution of each model upgrade

We have a kinematic single-track (KS) vehicle dynamics model running on real openpilot rlog driving data in **speed-known lateral-only** mode: measured `v` and measured `δ` are clamped at every integration step, so the only thing the model has to predict is the lateral channel (`ψ, ψ̇, a_y, x, y`). The predicted yaw rate `ψ̇` diverges from the measured `ψ̇` and we want to know **how much each potential improvement to the model closes that gap**.

## Deliverable

A `report.md` in the root of *this* folder, containing:

1. **Baseline.** Run the existing KS model on a representative sample of segments. Report overall RMSE of `ψ̇` (predicted vs measured) and RMSE broken down by maneuver regime: `straight`, `steady-state cornering`, `transient`. Define your regime thresholds and justify them in one paragraph.

2. **Additions.** Propose an *ordered* list of incremental upgrades to the model — each upgrade should plug a single identified weakness of the previous variant. Examples of legitimate additions include (but are not limited to): re-calibrating a KS parameter against the data, upgrading KS → ST (linear single-track with slip angles), tuning cornering stiffness `C_α` by residual minimisation, adding a small data-driven residual learner. For *each* addition:
   - Implement it.
   - Run it on the **same** segments as the baseline.
   - Recompute the regime-wise RMSE table.
   - Report `Δ_overall_vs_prev` and `% of remaining variance closed`.

3. **Attribution table.** Final table with one row per variant (including baseline). Columns:

   ```
   variant | RMSE_overall | RMSE_straight | RMSE_steady | RMSE_transient | Δ_overall_vs_prev | pct_variance_closed
   ```

   All RMSEs in rad/s. `pct_variance_closed` is `1 - (var(resid_this) / var(resid_baseline))` expressed as a percent.

4. **Figure.** Save a `report.png` in this folder overlaying predicted vs measured `ψ̇` for one transient-heavy segment, one trace per variant.

5. **Short narrative** (≤ 200 words at the bottom of `report.md`) — which addition mattered most and why, framed in terms of the *physics* of the lie each one plugs.

## Hard constraints

- **Read only** files inside this module folder, `./code`, and `./data` (note: `code` and `data` are symlinks at the module root). Do not `cat`, `ls`, or `find` anything in parent directories, sibling `webinar-*` folders, `KB00*`, or `~`. If you genuinely need information that is not in your sandbox, declare the gap in `report.md` under a "Missing information" section and proceed with the best assumption.
- Use **Ford segments only** for measured-vs-predicted residuals. Tesla rlogs do not have decodable yaw-rate truth.
- Each upgrade must be **incremental and individually scored**. No swapping to a wholly different model class without scoring the KS baseline first.
- Honor the *speed-known lateral-only* contract — do **not** unclamp `v` or `δ` as a "fix". That is out of scope; longitudinal residuals are not what we are measuring.
- Use the same segment list across all variants. State which segments you picked.
- All work must be reproducible: save any script you write under `./tools/` or as code blocks in `report.md`.

## Done criteria

- `report.md` exists at the root of this module folder.
- `report.md` contains the attribution table with at least one variant beyond the baseline.
- `report.png` exists and shows the overlay described above.
- The narrative names a single most-impactful addition and gives a physics-grounded reason.
