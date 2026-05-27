# Lateral-prediction improvement — agent 03 report

## 1. Headline
**Primary metric:** RMSE of yaw-rate prediction (rad/s), evaluated on a held-out 20 % segment-level test split, pooled across both Ford platforms (Mustang Mach-E MK1 and F-150 Lightning MK1) where the dataset includes a measured-yaw-rate truth channel.

| | Mach-E | F-150 Lightning | Mean |
|---|---|---|---|
| **Baseline RMSE (V0)** | 0.01087 rad/s | 0.01453 rad/s | **0.01270 rad/s** |
| **Final RMSE (V3)**    | 0.00847 rad/s | 0.00831 rad/s | **0.00839 rad/s** |
| **Relative reduction** | 22.1 %         | 42.8 %         | **33.9 %**     |

Across both platforms, the lateral (yaw-rate) RMSE was cut by roughly one third without touching `ks_model.py` — purely via fitted parameters and a swap from KS-kinematic to linear-bicycle-steady-state yaw.

## 2. What I implemented
The ladder is additive; each variant inherits the previous one's corrections.

- **V0 — baseline.** The KS prediction as recorded in the simdata CSVs: `ψ̇ = (v/L)·tan(δ_road)` with nominal `i_s` and zero offset.
- **V1 — steering-bias removal.** Subtract a per-platform scalar steering-wheel offset, estimated as the median `δ_road` on near-straight samples (|measured ψ̇| < 0.02 rad/s, v > 8 m/s). Fitted +0.30° (Mach-E) and −0.10° (F-150) at the steering wheel.
- **V2 — effective steer-ratio fit.** Replace the published nominal `i_s` with a single scalar `i_s_eff` per platform, fitted by least-squares on `ψ̇_meas = (v/L)·(δ − bias)/s`. Mach-E: 17.0 → **15.58**; F-150: 16.9 → **18.99**.
- **V3 — understeer-gradient correction (linear bicycle, steady-state).** Replace pure kinematic yaw with `ψ̇ = v·δ_eff / (L + K_us·v²)`. Fit `K_us` per platform by 1-D LS on `δ_eff − L·ψ̇/v = K_us · v·ψ̇`. Mach-E: K_us = 1.13 × 10⁻³ s²/m; F-150: 1.80 × 10⁻³ s²/m.

All three parameters were fit on the **train** split (≈80 % of segments, hashed deterministically) and the RMSE numbers above are reported on the disjoint **test** split. Only Ford segments were used because the Tesla simdata has no measured-yaw-rate truth channel (Tesla rlogs lack a decoded IMU on the open DBC).

## 3. Attribution

**Scheme A — marginal / sequential ablation** (drop in test-set RMSE when this variant is added on top of the previous one, divided by total V0→V3 drop):

| | Mach-E | F-150 Lightning |
|---|---|---|
| bias        | −5.0 % | −2.8 % |
| ratio       | +30.3 % | +69.2 % |
| understeer (K_us) | +74.7 % | +33.6 % |

**Scheme B — Shapley-style** (averaged marginal contribution across all 3! = 6 orderings of the three corrections):

| | Mach-E | F-150 Lightning |
|---|---|---|
| bias        | −3.0 %  | −3.6 % |
| ratio       | +58.3 % | +38.8 % |
| understeer  | +44.8 % | +64.8 % |

Bias is a near-zero / slightly negative contributor on both platforms — the offset is real but small enough that fitting it on the "near-straight" subset doesn't generalise. The two large-mass effects are the effective steer ratio and the understeer gradient, and Shapley redistributes some of V2's gain back to K_us because the ratio fit was partly compensating for missing understeer.

## 4. Surprises
- The fitted **effective steer ratio for the F-150 Lightning is 18.99 vs the published 16.9** — ~12 % higher. The Mach-E moves the other direction (15.58 vs 17.0). This is much larger than I expected for openpilot-canonical values that were claimed to be production-tuned.
- **Steering-bias correction by itself made things slightly worse** on both platforms. The near-straight cohort used to fit the bias is too small a slice to characterise the true offset, and the rest of the distribution doesn't share the same median. A combined fit (bias + ratio jointly) would likely recover the missing 5 % or so.
- The understeer coefficient `K_us` for the F-150 (1.8 × 10⁻³ s²/m) is notably larger than the Mach-E's (1.1 × 10⁻³), consistent with the Lightning's much heavier curb weight (3084 kg vs 2336 kg) and higher CoG — a sanity check the fits passed.
- The simdata CSV is rich enough that this exercise needed zero re-running of `simulate_ks` — every column required was already in `sim.csv` from `generate_simdata_ford.py`.

## 5. Limitations
- **Tesla excluded.** Tesla simdata has no measured yaw-rate truth channel, so I cannot quantify improvement there. The same parameter fits could be ported but would need an independent truth source (IMU reverse-engineering on the Tesla party DBC).
- **Linear-bicycle, not ST proper.** I used the steady-state form `ψ̇ = v·δ / (L + K_us·v²)`, not the transient single-track ODE with separate `C_α,f`, `C_α,r`. The full ST integration would likely shave another few percent in transients but would require touching `ks_model.py`. I deliberately stayed in post-processing scope to keep the ablation clean.
- **No tyre saturation / a_y-magnitude split.** All samples weighted equally; at high `|a_y|` (> 4 m/s²) the linear assumption breaks. A separate analysis would benefit from stratifying by `|a_y|`.
- **No cross-validation across segments / drivers.** The 80/20 split is a single shuffle. K-fold would give an uncertainty band on each attribution share.
- **Time budget.** Did not have time to write a closed-form joint LS fit for (bias, ratio_scale, K_us) — fitting them sequentially is suboptimal and explains why Shapley shares differ from sequential.
- **Honour-bound restrictions:** I did not read any sibling-agent folder, any `webinar-angle-*/modulo-*/`, or `webinar-00/`. The hook did not visibly block me.

Outputs saved:
- `tools/improve_lateral.py`
- `out/run2.txt`

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Ford simdata only — Tesla has no yaw-rate truth channel in this dataset, so reported gains cover Mach-E and F-150 Lightning. No reads outside agent-03/, ./code/, ./data/."
```
