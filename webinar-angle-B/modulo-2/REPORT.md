# Module 2 — Lateral fidelity of the KS model on Ford platforms

Working directory: `webinar-angle-B/modulo-2/`. All numbers below are pooled
across both available segments per platform (2 × 2898 rows @ 50 Hz). Truth
columns are `yaw_rate_meas_rads` and `a_lat_meas_mps2`; residuals are
`measured − predicted`.

Mode: speed-known lateral-only (`clamp_v_to_measured=True`,
`clamp_delta_to_measured=True`). Kept unchanged for all variants.

## How to reproduce

```bash
cd webinar-angle-B/modulo-2
python3 ablation.py
```

`ablation.py` reads the existing Ford sim CSVs, recomputes lateral
predictions under five variants, and prints the table reproduced below.

## 1. Baseline residual per platform

| Platform | yr RMSE (°/s) | a_y RMSE (m/s²) | yr corr | a_y corr | yr bias (°/s) |
|---|---:|---:|---:|---:|---:|
| FORD_MUSTANG_MACH_E_MK1  | **0.505** | **0.062** | 0.463 | 0.804 | +0.316 |
| FORD_F_150_LIGHTNING_MK1 | **1.104** | **0.443** | 0.987 | 0.789 | −0.873 |

### Regimes where baseline is worst

| Bin                | Mach-E yr RMSE | F-150 yr RMSE |
|---|---:|---:|
| v ∈ [0, 5)   m/s   | 0.268 | 0.530 |
| v ∈ [5, 15)  m/s   | 0.614 | 1.122 |
| v ∈ [15, 25) m/s   | 0.157 | 0.739 |
| v ∈ [25, ∞)  m/s   | —     | 1.369 |
| |a_y| ∈ [0,1) m/s² | 0.505 | 1.054 |
| |a_y| ∈ [1,3) m/s² | —     | 1.775 |

Two patterns dominate: (a) persistent yaw-rate bias of opposite signs
on the two platforms; (b) error grows with v and |a_y| on the F-150 —
exactly the regime where KS's no-slip assumption breaks.

## 2. Improvements proposed

1. **Yaw-rate bias correction (V2).** Non-zero mean residual suggests
   steering zero offset or sensor bias. Measure: subtract mean residual.
2. **Steering offset+scale calibration (V3).** `i_s` is an openpilot
   prior, not regressed on this vehicle. Fit `δ_eff=(δ−δ0)·k` by
   linear regression of ψ̇_meas vs `(v/L)·δ` and `(v/L)`.
3. **Understeer-gradient term (V4):** step up to steady-state bicycle
   `ψ̇=v·δ_eff/(L+K_u·v²)`; fit `K_u`.
4. **First-order steering lag (V5):** `δ_lag = LPF(δ_eff, τ)`.
5. **Not implemented**: full ST with linear tyres (parameters already
   available in `MachEST` / `F150LightningST`); Pacejka for high-G
   (the F-150 |a_y|∈[1,3) bin is the worst); per-segment learned
   residual on top of the physics stack.

## 3. Improvements implemented + ablation table

Code: all in `ablation.py` (self-contained, no edits to `code/`).

### Ford Mustang Mach-E MK1

| Variant | yr RMSE (°/s) | Δ vs V1 | rel Δ | a_y RMSE | ψ̇ corr |
|---|---:|---:|---:|---:|---:|
| V1 KS recompute (baseline) | 0.505 | — | — | 0.062 | 0.463 |
| V2 + ψ̇ bias (+0.316°/s) | **0.394** | −0.111 | −22.0% | 0.114 | 0.463 |
| V3 + steering cal (δ0=−0.0012 rad, k=0.910) | 0.455 | −0.050 | −9.9% | 0.108 | 0.331 |
| V4 + understeer (K_u=4.08e-3) | 0.439 | −0.066 | −13.1% | 0.090 | 0.420 |
| V5 + steering lag (τ=84 ms) | 0.439 | −0.066 | −13.1% | 0.090 | 0.423 |

### Ford F-150 Lightning MK1

| Variant | yr RMSE (°/s) | Δ vs V1 | rel Δ | a_y RMSE | ψ̇ corr |
|---|---:|---:|---:|---:|---:|
| V1 KS recompute (baseline) | 1.104 | — | — | 0.443 | 0.987 |
| V2 + ψ̇ bias (−0.873°/s) | 0.676 | −0.428 | −38.8% | 0.393 | 0.987 |
| V3 + steering cal (δ0=+0.00245 rad, k=0.932) | 0.521 | −0.583 | −52.8% | 0.390 | 0.991 |
| V4 + understeer (K_u=1.56e-3) | 0.440 | −0.664 | −60.1% | 0.270 | 0.996 |
| V5 + steering lag (τ=31 ms) | **0.413** | −0.691 | −62.6% | 0.269 | 0.996 |

## 4. Ranking of impact

1. **Steering offset+scale calibration (V3)** is the biggest
   physically-motivated win on the F-150 (subsumes the constant bias).
   Cheap, interpretable, deploys at the adapter layer.
2. **Understeer-gradient term (V4)** is the second biggest win on the
   F-150 (further −0.08°/s ψ̇ and −0.12 m/s² a_y). Physically
   motivated (heavy truck, large I_z).
3. **ψ̇ bias only (V2)** is a cheap stop-gap — best Mach-E ψ̇ number,
   actually — but symptom-fixes what V3 explains physically.
4. **Steering lag (V5)** marginal on both platforms; consider only in
   transient-heavy datasets.
5. **Not worth pursuing here:** more model sophistication on Mach-E
   (residual is largely urban-driving noise; corr ≈ 0.46 even post-fix).
   Need a higher-G Mach-E segment to validate ST / Pacejka.

## 5. Limitations

- Only 2 segments per platform (~58 s each). All fits are in-sample.
  No held-out validation; δ-cal numbers should be cross-validated
  before trusting in production.
- Mach-E pool has zero |a_y| > 1 m/s². High-G regime (where KS is
  known to fail) is unrepresented for this platform.
- I cannot verify from inside this module whether the adapter applied
  the steering-sign flip warned about in AGENTS.md. Part of the
  constant ψ̇ bias might be a sign-convention artefact silently
  absorbed by V2/V3.
- Full ST with linear tyres and Pacejka not implemented in this budget.
- CAN-decode deps (cantools/pycapnp/zstandard) not installed; existing
  CSVs treated as authoritative.
