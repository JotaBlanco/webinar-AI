# residual_gb — assessment

## Pooled scores (full sim/segments)

| metric | V1 | residual_gb | delta |
|---|---|---|---|
| yaw RMSE (rad/s) | 0.01061 | 0.00743 | **-30.0%** |
| CTE RMSE (m)     | 75.65   | 59.44   | **-21.4%** |

## Per-platform

| platform | V1 yaw | GB yaw | V1 CTE | GB CTE |
|---|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.01273 | 0.00720 | 62.18 | 50.59 |
| FORD_MUSTANG_MACH_E_MK1  | 0.01363 | 0.00691 | 98.68 | 69.07 |
| HYUNDAI_IONIQ_5          | 0.00893 | 0.00762 | 69.53 | 57.90 |
| TESLA_MODEL_3            | n/a     | n/a     | n/a   | n/a   |

## Holdout (route-grouped 80/20)

| platform | dev yaw V1 | dev yaw GB | dev CTE V1 | dev CTE GB |
|---|---|---|---|---|
| Lightning | 0.00369 | 0.00357 | 17.68 | 8.70  |
| Mach-E    | 0.00853 | 0.00740 | 209.65 | 168.44 |
| Ioniq-5   | 0.00726 | 0.00711 | 63.28 | 54.11  |

The gain holds out-of-route, especially on CTE — direct evidence the structural correction is real, not memorisation.

## Verdict

**Ship.** Structurally novel from V1 (non-linear, learned, sample-wise residual head). Strict improvement on both KPIs both in-sample and held-out.

## Caveats

- Tree-based residual head is opaque; we cannot read off what physics it is recovering. The diagnostic that "30% of V1 residual lives in transients" suggests the GB head is mostly fitting transient-regime dynamics that V1's single-pole lag mis-shapes.
- We sub-sample to 400k rows during fit for speed; full-data fit would gain a couple of basis points more on Ioniq-5.
- Per-segment δ₀ for Mach-E / Ioniq is **recomputed at predict time** — so it carries through to the GB features (`yr_v1` already reflects it).
