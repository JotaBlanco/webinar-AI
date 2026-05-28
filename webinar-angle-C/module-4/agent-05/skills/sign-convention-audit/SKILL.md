---
name: sign-convention-audit
description: Audit a sim.csv (or a batch under a platform tree) for the residual-sign convention declared in AGENTS.md. Catches the exact ratchet-#1 failure mode — `yaw_rate_resid_rads` stored as `meas − pred` instead of the project's `pred − meas`. RMSE-blind code wouldn't notice; any signed analytic (bias removal, lag direction, sign of `k`) would silently invert.
when-to-load: Before trusting any signed quantity derived from `yaw_rate_resid_rads` (bias, gain, lag direction, regression coefficients). Also good to load when `schema_check.py` fails with "yaw_rate_resid sign/value mismatch".
inputs: Path to a sim.csv OR a platform directory.
outputs: PASS / FAIL with the detected stored convention (`pred-meas` or `meas-pred`) and a count of files in each convention.
load-cost: ~150 tokens metadata, ~250 tokens body.
---

# sign-convention-audit

## When to load

`schema_check.py` enforces `resid == pred − meas` within 1e-6. If it fails with sign-related text, this skill tells you *which* convention the file actually stores. Necessary because the project's ratchet-#1 failure was someone computing `bias = median(resid)` while assuming `meas − pred` — and the corrupting fact is that the bias number magnitude is the *same*, only the sign is flipped, so RMSE-only validation never catches it.

## Procedure

For each `sim.csv`:

1. Compute `delta_pm = max|resid − (pred − meas)|`.
2. Compute `delta_mp = max|resid − (meas − pred)|`.
3. If `delta_pm < 1e-6` -> stored as `pred − meas` (CANONICAL, PASS).
4. Elif `delta_mp < 1e-6` -> stored as `meas − pred` (FLIPPED, FAIL — every signed downstream analytic must be sign-flipped before use).
5. Else -> neither (genuine corruption — investigate separately).

## Why it matters

- `bias = mean(stored_resid)` flips sign under convention error -> any post-subtraction *adds* the bias instead of removing it.
- Steering-gain fits keyed off `corr(stored_resid, δ_road)` invert their slope sign.
- Lag scans that pick `argmin RMSE(stored_resid_shifted)` are blind to this (RMSE is symmetric), so a passing lag value is not evidence the rest of your pipeline is OK.

## Disposition

If FAIL is detected, **do not** patch the CSV — fix the producer (`code/generate_simdata_ford.py`) so future runs are correct, and in your immediate variant ladder explicitly compute the residual as `pred - meas` from the two truth columns, *ignoring* the stored `yaw_rate_resid_rads`. That is what this module's ladder does.
