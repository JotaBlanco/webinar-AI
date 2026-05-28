# Agent 01 — raw-model / idea-02

## 1. Headline numbers

| Metric | Baseline | Final |
|---|---|---|
| **Closed-loop v RMSE (Mach-E, all-regime, 58 s segments)** | 5.33 m/s (hold v0 constant) | **7.97 m/s** (worse than baseline) |
| **Closed-loop v RMSE (F-150 Lightning, all-regime)** | 5.18 m/s | **8.99 m/s** (worse) |
| **Closed-loop v RMSE (Tesla Model 3, all-regime)** | 5.19 m/s | **9.07 m/s** (worse) |
| Open-loop one-step v RMSE (all platforms) | n/a | **0.01–0.04 m/s** |
| Open-loop one-step a RMSE (a-residual) | n/a | **0.57–0.67 m/s²** |
| Reference crutch: integrate sensed `a_long_meas` | — | 0.01 m/s (Tesla, tautology) / 2.0–3.0 m/s (Ford, real IMU) |

**Primary metric** = closed-loop integrated v RMSE over a full ~58 s segment, model fed only by *commanded* inputs (`accel_pedal_pct`, brake binary) and its own internal speed state. By that metric the model **does not yet stand on its own** — it loses to a zero-knowledge constant-speed baseline.

## 2. What I implemented

- A per-platform linear/quadratic-drag longitudinal acceleration model: `a = c_thr·pedal + c_brk·brake_on + c_v·v + c_v|v|·v|v| + c_0`, fit by OLS against measured `a_long_mps2`. (`tools/build_long_model.py`)
- Closed-loop forward Euler integrator on top of that model, with `[a]` clipped to `[-10, 6] m/s²` and `[v]` clipped to `[0, 70] m/s` to prevent divergence on bad coefficient fits.
- Three baselines reported alongside: (a) constant-speed `v(t)=v0`, (b) "integrate the sensed acceleration" crutch, (c) one-step `v + dt·a_pred`.
- Outlier filter: drop any segment with `|a_long| > 15 m/s²` or `v` outside `[-1, 60] m/s` (the F-150 set contained a segment with `a_long` peaking at 1057 m/s² — clearly a CAN-decode glitch).

## 3. How I validated

- **Mode A — open-loop one-step (a-residual)**: predict `a_pred` from inputs and *measured* `v_meas`; compare to measured `a_long`. RMSE = 0.57 (Tesla), 0.57 (Mach-E), 0.62 (F-150) m/s².
- **Mode B — open-loop one-step v**: `v_meas[k] + dt·a_pred[k]` vs `v_meas[k+1]`. RMSE = 0.01–0.04 m/s (uninformative at `dt=0.02` s — any model passes this).
- **Mode C — closed-loop integration (the real test)**: full ~58 s segment, model receives **only** `accel_pedal_pct` (sensed driver intent), `brake_pressed` (sensed binary), and its own internal `v_pred` state. Initial condition `v(0) = v_meas(0)`. RMSE evaluated over full segment.
- **Train/test split**: 70/30 by segment (seeded). Mach-E: 222 train / 95 test; F-150: 161 / 69; Tesla: 720 / 304.

**Inputs declared by source** — pedal % and brake-pressed are *sensed driver-input channels* (CAN signals from the driver pedals), not commanded by the model. So even the "final" model is not fully open-loop autonomous — it's "speed-free, but driver-input-known." That is the appropriate framing to unblock the lateral model from the v_meas clamp; the actual autonomy stack would substitute its own commanded pedal/brake here.

## 4. Regime breakdown (closed-loop v RMSE in m/s, test-set pooled samples)

| Platform | regime | n samples | model | const-v0 | int(a_meas) | a_rmse |
|---|---|---:|---:|---:|---:|---:|
| Mach-E | cruise | 151,664 | **11.10** | 5.56 | 4.09 | 0.29 |
| Mach-E | accel | 32,949 | **8.45** | 7.88 | 4.72 | 1.05 |
| Mach-E | brake | 34,511 | **9.06** | 8.71 | 4.06 | 1.03 |
| Mach-E | coast | 106,036 | **11.04** | 6.09 | 3.75 | 0.33 |
| F-150 | cruise | 89,034 | **13.23** | 5.70 | 2.98 | 0.41 |
| F-150 | accel | 27,053 | **8.46** | 8.28 | 3.29 | 0.94 |
| F-150 | brake | 34,587 | **11.66** | 9.20 | 2.68 | 0.98 |
| F-150 | coast | 82,983 | **11.39** | 3.46 | 2.45 | 0.39 |
| Tesla | cruise | 494,172 | **10.34** | 5.62 | 0.02 | 0.31 |
| Tesla | accel | 107,919 | **10.55** | 8.18 | 0.04 | 0.87 |
| Tesla | brake | (mask broken — see surprises) | — | — | — | — |

Model worst regimes are **cruise** and **coast** — exactly where small bias in the constant/drag terms compounds over time. Best regime is **accel** because the throttle gain term dominates and the model captures it.

## 5. Surprises

- **Tesla `a_long_mps2` is `dv/dt` of `v_meas`** — derived from wheel speed in the adapter, not from an independent IMU. The Tesla "baseline: integrate sensed a" gives 0.01 m/s by tautology, not by good IMU. This is called out in the README's longitudinal decomposition note but easy to miss.
- **Tesla `brake_pedal_state` is enum-coded** (`==2` always = released; brake-press uses a different value never seen in sample). My regime mask `(state > 0)` is therefore True everywhere — Tesla brake regime collapsed to "all". Real brake on Tesla needs proper enum decode.
- **F-150 segment with `a_long = 1057 m/s²`** — a CAN decode artefact in the simdata. Outlier filter dropped it.
- Mean `a_long` across all segments is ~ –0.02 m/s² — almost zero, as expected for a balanced drive set. The fit's `c_0 = –0.13` constant-drag term is a model error, not a data property.
- One-step v error (1–4 cm/s) is **uninformative** at 50 Hz — any model with bounded `a` passes it. Closed-loop integration RMSE is the only meaningful test.

## 6. Limitations

- **The model is worse than a zero-knowledge baseline in closed-loop.** A linear-in-pedal model with constant drag cannot capture the regen-vs-friction asymmetry, motor torque saturation at low speed, or road-grade contributions. Likely fixes: split throttle into low-speed/high-speed regimes, use the Tesla `di_torque_actual_nm` channel directly (cleaner than pedal %), include grade via gravity-corrected `a_long - dv_meas/dt`, and constrain `c_0 = 0` by construction.
- **Did not access** the docs at `../models.md` / `../adapters.md` (cross-angle module reads not permitted) — relied only on `code/_README.md` and the code itself.
- **No platform-specific physics priors** (mass, frontal area, Crr, motor torque curves) were brought in — pure data-driven regression.
- **Train/test split was per-segment random**, not per-device or per-route. Mild leakage possible.
- **Tesla brake-pressed could not be recovered** without proper enum decode; my brake regime is broken for Tesla.
- **No tuning loop** — single OLS fit. Did not iterate on feature engineering once the structural drift problem was visible.
- **No `Write` blocking encountered.**

Files of interest:
- `tools/build_long_model.py`
- `out/summary.json`
- `out/per_seg_*.json`

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "All work confined to agent-01/. Did not read sibling agents, other idea-*/, webinar-angle-*/, or webinar-00/. One outlier segment (F-150, peak a=1057 m/s2) was filtered out. Tesla brake enum decode is broken in the source data (always =2), making the Tesla brake regime mask meaningless."
```
