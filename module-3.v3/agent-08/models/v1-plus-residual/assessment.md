# Assessment — v1-plus-residual

Scored on full `data/sim/segments/` (yaw RMSE filtered to `v_mps > 2`, matching
the canonical scorer's sample filter).

## Pooled (3 truth platforms)

| metric   | V1     | v1-plus-residual | delta    |
|----------|--------|------------------|----------|
| yaw RMSE | 0.00762 | 0.00738          | -3.1%    |
| CTE RMSE | 75.65  | 71.77            | -5.1%    |

## Per platform

| platform               | metric | V1      | residual | delta   |
|------------------------|--------|---------|----------|---------|
| FORD_F_150_LIGHTNING_MK1 | yaw    | 0.00566 | 0.00537  | -5.2%   |
|                        | CTE    | 62.18   | 64.23    | +3.3% (regress) |
| FORD_MUSTANG_MACH_E_MK1 | yaw    | 0.00859 | 0.00814  | -5.3%   |
|                        | CTE    | 98.68   | 93.58    | -5.2%   |
| HYUNDAI_IONIQ_5        | yaw    | 0.00766 | 0.00751  | -2.0%   |
|                        | CTE    | 69.53   | 64.85    | -6.7%   |

Lightning CTE regresses slightly — the linear correction trades a tiny amount
of CTE for a larger yaw win. On the pooled metric it's a clear net positive.

## Residual character after correction

Yaw mean residual drops toward zero on each platform (Mach-E's +3.5e-3 mean
bias is the main thing the bias and `v*delta`-style features absorb). The
remaining residual is high-frequency and unattacked by this linear shape.

## Verdict

**Ship.** Beats V1 on both pooled metrics, and on 5 of 6 per-platform cells.
The one regression (Lightning CTE) is +3% on a platform that's already at
~noise floor. Net win.
