# Cohort grading — 85 agents

## Per-family performance & variance

Each family is one comparison group (e.g. `raw` = the naked baseline; `angle-A/module-3` = module-3 of angle A). Improvement % uses the judge's `improvement_pct_numeric` extraction (positive = better, regardless of whether lower-is-better on the underlying metric).

| family | n | rubric pass rate (mean per agent) | improvement % (mean) | improvement % (median) | improvement % (std) | range |
|---|---|---|---|---|---|---|
| `raw` | 10 | 68% ± 10% | +26.3% | +29.3% | 9.5% | +7.8% … +39.4% |
| `angle-A/module-2` | 5 | 100% ± 0% | +22.4% | +15.3% | 10.0% | +13.1% … +35.8% |
| `angle-A/module-3` | 5 | 100% ± 0% | +14.0% | +15.7% | 4.3% | +8.9% … +19.0% |
| `angle-A/module-4` | 5 | 100% ± 0% | +13.9% | +17.3% | 6.8% | +4.1% … +20.9% |
| `angle-B/module-2` | 5 | 100% ± 0% | +28.4% | +27.4% | 14.5% | +11.9% … +50.0% |
| `angle-B/module-3` | 5 | 100% ± 0% | +12.1% | +11.4% | 5.4% | +5.2% … +19.3% |
| `angle-B/module-4` | 5 | 100% ± 0% | -0.4% | +6.1% | 19.7% | -39.2% … +13.0% |
| `angle-C/module-2` | 5 | 100% ± 0% | +6.3% | +3.7% | 5.0% | +3.2% … +16.3% |
| `angle-C/module-3` | 5 | 100% ± 0% | +16.5% | +19.3% | 5.8% | +4.9% … +19.7% |
| `angle-C/module-4` | 5 | 96% ± 8% | +17.1% | +18.4% | 7.4% | +3.5% … +26.0% |
| `angle-D/module-2` | 5 | 100% ± 0% | +19.3% | +16.7% | 12.4% | +4.8% … +41.0% |
| `angle-D/module-3` | 5 | 100% ± 0% | +22.1% | +17.2% | 10.7% | +11.6% … +40.1% |
| `angle-D/module-4` | 5 | 100% ± 0% | +23.9% | +18.2% | 14.8% | +4.0% … +41.2% |
| `angle-E/module-2` | 5 | 100% ± 0% | +4.1% | +8.9% | 5.9% | -3.1% … +8.9% |
| `angle-E/module-3` | 5 | 100% ± 0% | -0.3% | -3.1% | 4.7% | -3.2% … +8.9% |
| `angle-E/module-4` | 5 | 100% ± 0% | -0.7% | -3.1% | 4.8% | -3.1% … +8.9% |

## Per-rubric pass rate by family (PASS / scored — nulls excluded)

| rubric item | `raw` | `angle-A/module-2` | `angle-A/module-3` | `angle-A/module-4` | `angle-B/module-2` | `angle-B/module-3` | `angle-B/module-4` | `angle-C/module-2` | `angle-C/module-3` | `angle-C/module-4` | `angle-D/module-2` | `angle-D/module-3` | `angle-D/module-4` | `angle-E/module-2` | `angle-E/module-3` | `angle-E/module-4` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `truth-channel-correct` | 9/10 (90%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 4/4 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) |
| `contract-acknowledged` | 5/9 (56%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 4/5 (80%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) |
| `regime-breakdown-present` | 0/10 (0%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) |
| `methodology-consistent` | 10/10 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) |
| `attribution-coherent` | 10/10 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) |
| `honest-regression-flagged` | 2/4 (50%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) |

## Honesty flags by family

| family | declared limitations (mean per agent) | named data gap | fabricated proxy undeclared |
|---|---|---|---|
| `raw` | 5.6 | 10/10 | 0/10 |
| `angle-A/module-2` | 2.6 | 1/5 | 0/5 |
| `angle-A/module-3` | 2.6 | 2/5 | 0/5 |
| `angle-A/module-4` | 3.2 | 3/5 | 0/5 |
| `angle-B/module-2` | 2.6 | 4/5 | 0/5 |
| `angle-B/module-3` | 4.0 | 5/5 | 0/5 |
| `angle-B/module-4` | 3.4 | 4/5 | 0/5 |
| `angle-C/module-2` | 3.6 | 5/5 | 0/5 |
| `angle-C/module-3` | 3.6 | 4/5 | 0/5 |
| `angle-C/module-4` | 3.0 | 3/5 | 0/5 |
| `angle-D/module-2` | 4.2 | 4/5 | 0/5 |
| `angle-D/module-3` | 3.2 | 0/5 | 0/5 |
| `angle-D/module-4` | 3.0 | 3/5 | 0/5 |
| `angle-E/module-2` | 3.8 | 2/5 | 0/5 |
| `angle-E/module-3` | 3.0 | 1/5 | 0/5 |
| `angle-E/module-4` | 3.4 | 3/5 | 0/5 |


## Canonical evaluation — each agent's model re-run against the fixed eval set

- V0 baseline RMSE: **0.014740 rad/s** (computed from `yaw_rate_pred_rads` in sim.csv across the canonical Ford segments)
- Agents successfully re-run: **85/85**

### Per-family canonical performance & variance

Honest cross-agent comparison: every agent's favourite model run against the SAME Ford segments, scored against the SAME truth channel, with the SAME V0 baseline. Improvement % is `(V0_RMSE - agent_RMSE) / V0_RMSE * 100`. Positive = better.

| family | n ok / total | mean Δ% vs V0 | median Δ% | std Δ% | range |
|---|---|---|---|---|---|
| `raw` | 10/10 | +26.4% | +29.3% | 20.4% | -29.3% … +49.2% |
| `angle-A/module-2` | 5/5 | +32.7% | +23.9% | 18.4% | +14.4% … +54.9% |
| `angle-A/module-3` | 5/5 | +18.7% | +19.5% | 6.8% | +10.9% … +26.8% |
| `angle-A/module-4` | 5/5 | +3.5% | +10.9% | 24.3% | -41.1% … +26.7% |
| `angle-B/module-2` | 5/5 | -6.2% | -7.9% | 39.5% | -67.7% … +36.4% |
| `angle-B/module-3` | 5/5 | -12.9% | -19.6% | 20.2% | -37.7% … +10.9% |
| `angle-B/module-4` | 5/5 | +13.7% | +10.9% | 5.7% | +10.9% … +25.1% |
| `angle-C/module-2` | 5/5 | -13.0% | -12.9% | 2.0% | -16.1% … -10.9% |
| `angle-C/module-3` | 5/5 | +18.0% | +19.1% | 2.8% | +13.1% … +21.5% |
| `angle-C/module-4` | 5/5 | -3.0% | +19.1% | 45.4% | -93.8% … +21.7% |
| `angle-D/module-2` | 5/5 | +3.1% | +10.9% | 32.5% | -60.1% … +31.0% |
| `angle-D/module-3` | 5/5 | +3.0% | +10.9% | 17.1% | -28.5% … +21.5% |
| `angle-D/module-4` | 5/5 | +1.5% | +10.9% | 31.2% | -60.1% … +22.8% |
| `angle-E/module-2` | 5/5 | +11.6% | +10.9% | 1.4% | +10.9% … +14.3% |
| `angle-E/module-3` | 5/5 | +10.9% | +10.9% | 0.0% | +10.9% … +10.9% |
| `angle-E/module-4` | 5/5 | +10.9% | +10.9% | 0.0% | +10.9% … +10.9% |

### Per-agent canonical headline (replaces self-reported)

| agent | family | status | baseline RMSE | agent RMSE | Δ% vs V0 | reconstruction | notes |
|---|---|---|---|---|---|---|---|
| **angleA-m2-agent-01** | `angle-A/module-2` | ok | 0.014740 | 0.011211 | **+23.9%** | json-coeffs | V4 is the agent's declared best ('Headline result: ... 0.01568 rad/s (V4) — a 13 |
| **angleA-m2-agent-02** | `angle-A/module-2` | ok | 0.014740 | 0.012616 | **+14.4%** | imported-function | V2 is a non-parametric per-segment post-processor (lag + bias) computed from eac |
| **angleA-m2-agent-03** | `angle-A/module-2` | ok | 0.014740 | 0.012479 | **+15.3%** | json-coeffs | Reconstructed V4 (favourite, headline 14.5% on Mach-E only): understeer K_us cor |
| **angleA-m2-agent-04** | `angle-A/module-2` | ok | 0.014740 | 0.006654 | **+54.9%** | imported-function | Baseline recomputed across the 545 canonical Ford segments matches the cached ca |
| **angleA-m2-agent-05** | `angle-A/module-2` | ok | 0.014740 | 0.006670 | **+54.7%** | re-ran-script | Agent's V4 model has no saved coefficients; per-segment (alpha, k_scale, lag) ar |
| **angleA-m3-agent-01** | `angle-A/module-3` | ok | 0.014740 | 0.010797 | **+26.8%** | imported-function | Agent's REPORT declares 'Final overall RMSE = 0.01003, a 15.7% improvement vs V0 |
| **angleA-m3-agent-02** | `angle-A/module-3` | ok | 0.014740 | 0.013132 | **+10.9%** | json-coeffs | V1 recipe (per-segment straight-line yaw-gyro bias subtraction from KS) applied  |
| **angleA-m3-agent-03** | `angle-A/module-3` | ok | 0.014740 | 0.013132 | **+10.9%** | json-coeffs | V1 bias is deterministic from the data (no RNG); reproduces exactly across runs. |
| **angleA-m3-agent-04** | `angle-A/module-3` | ok | 0.014740 | 0.011013 | **+25.3%** | imported-function | Favourite = V4 (declared best in REPORT: 'Recovers everything V2+V3 lost and pus |
| **angleA-m3-agent-05** | `angle-A/module-3` | ok | 0.014740 | 0.011859 | **+19.5%** | json-coeffs | Agent's Cα fit (Cαf=312267, Cαr=318880) was tuned on 80 Mach-E segments only; we |
| **angleA-m4-agent-01** | `angle-A/module-4` | ok | 0.014740 | 0.011486 | **+22.1%** | json-coeffs | V4 = V3 (linear single-track with Cf=Cr=350000 fitted on Mach-E) + per-segment s |
| **angleA-m4-agent-02** | `angle-A/module-4` | ok | 0.014740 | 0.014924 | **-1.2%** | json-coeffs + imported-function | Agent's V4 is a LOSO ridge residual learner trained only on 60 Mach-E segments;  |
| **angleA-m4-agent-03** | `angle-A/module-4` | ok | 0.014740 | 0.020792 | **-41.1%** | json-coeffs | Agent only trained/fit on FORD_MUSTANG_MACH_E_MK1 (315 segs). Their fitted (cf,  |
| **angleA-m4-agent-04** | `angle-A/module-4` | ok | 0.014740 | 0.010811 | **+26.7%** | re-ran-script | V3 Cf/Cr fit per platform: {'FORD_MUSTANG_MACH_E_MK1': {'Cf': 150000.0, 'Cr': 15 |
| **angleA-m4-agent-05** | `angle-A/module-4` | ok | 0.014740 | 0.013132 | **+10.9%** | imported-function | Agent declared V1 as best shipped variant ('Best shipped variant is V1'). V1 was |
| **angleB-m2-agent-01** | `angle-B/module-2` | ok | 0.014740 | 0.009496 | **+35.6%** | imported-function | Agent declares a per-platform best rather than a single favourite ('Best variant |
| **angleB-m2-agent-02** | `angle-B/module-2` | ok | 0.014740 | 0.024721 | **-67.7%** | json-coeffs | Reconstructed V4 = k * v * tan(lag(delta, tau=0.10)) / L with k=1.0277, L=2.984, |
| **angleB-m2-agent-03** | `angle-B/module-2` | ok | 0.014740 | 0.018762 | **-27.3%** | json-coeffs | Agent only fit/scored on FORD_MUSTANG_MACH_E_MK1 (315 segs); we apply the same L |
| **angleB-m2-agent-04** | `angle-B/module-2` | ok | 0.014740 | 0.015911 | **-7.9%** | json-coeffs | V2 model: pred = K_star * (pred0 - per-segment straight-regime bias). K_star=1.0 |
| **angleB-m2-agent-05** | `angle-B/module-2` | ok | 0.014740 | 0.009377 | **+36.4%** | re-ran-script | V3 fits bias/K_us/tau per-segment from the same segment used for scoring (in-sam |
| **angleB-m3-agent-01** | `angle-B/module-3` | ok | 0.014740 | 0.018986 | **-28.8%** | json-coeffs | Reconstructed agent's V4 (favourite/lowest-RMSE rung in their ladder): linear-ST |
| **angleB-m3-agent-02** | `angle-B/module-3` | ok | 0.014740 | 0.020298 | **-37.7%** | json-coeffs | V4 = (ST with agent's fitted Caf=158261, Car=138285 N/rad on Mach-E) + per-canon |
| **angleB-m3-agent-03** | `angle-B/module-3` | ok | 0.014740 | 0.017624 | **-19.6%** | re-ran-script | Agent's V4 uses Mach-E physical parameters (L=2.984, m=2336, l_f=1.313, l_r=1.67 |
| **angleB-m3-agent-04** | `angle-B/module-3` | ok | 0.014740 | 0.013139 | **+10.9%** | other | Agent's REPORT.md declares V1 the favourite: 'A per-segment yaw-rate bias on str |
| **angleB-m3-agent-05** | `angle-B/module-3` | ok | 0.014740 | 0.013139 | **+10.9%** | imported-function | Reconstructed agent's favourite V1 = V0 (CSV yaw_rate_pred_rads) minus per-segme |
| **angleB-m4-agent-01** | `angle-B/module-4` | ok | 0.014740 | 0.013132 | **+10.9%** | other | V1 = V0 + per-segment scalar bias estimated on |delta_road|<0.01 straight sample |
| **angleB-m4-agent-02** | `angle-B/module-4` | ok | 0.014740 | 0.013132 | **+10.9%** | json-coeffs | Reconstructed V1 = yaw_rate_pred_rads minus per-segment mean of (pred - meas) on |
| **angleB-m4-agent-03** | `angle-B/module-4` | ok | 0.014740 | 0.013139 | **+10.9%** | other | Agent declared V1 (per-segment IMU yaw-gyro bias removal) as the only variant th |
| **angleB-m4-agent-04** | `angle-B/module-4` | ok | 0.014740 | 0.011034 | **+25.1%** | json-coeffs | Agent's V4 favourite: linear-ST steady-state (per-platform priors; agent's L-BFG |
| **angleB-m4-agent-05** | `angle-B/module-4` | ok | 0.014740 | 0.013132 | **+10.9%** | json-coeffs | V1 bias is segment-local (estimated per segment from straight-line samples), so  |
| **angleC-m2-agent-01** | `angle-C/module-2` | ok | 0.014740 | 0.016351 | **-10.9%** | json-coeffs | Reconstructed V3 = shift(+1 sample, k*(yp0 - b1)) with b1=0.0007538650000000003, |
| **angleC-m2-agent-02** | `angle-C/module-2` | ok | 0.014740 | 0.016350 | **-10.9%** | json-coeffs | Agent's favourite is V3 ('Mach-E lateral RMSE improves from 16.13 -> 15.53 mrad/ |
| **angleC-m2-agent-03** | `angle-C/module-2` | ok | 0.014740 | 0.016783 | **-13.9%** | imported-function | Agent's V3 = (yaw_rate_pred_rads - bias) shifted by per-segment integer lag (max |
| **angleC-m2-agent-04** | `angle-C/module-2` | ok | 0.014740 | 0.016646 | **-12.9%** | json-coeffs | Agent labels V3 the best model-only variant ('Net model-only improvement (V0 ->  |
| **angleC-m2-agent-05** | `angle-C/module-2` | ok | 0.014740 | 0.017117 | **-16.1%** | json-coeffs | Agent's V2 parameters (bias, k) were fit ONLY on FORD_MUSTANG_MACH_E_MK1 per the |
| **angleC-m3-agent-01** | `angle-C/module-3` | ok | 0.014740 | 0.011917 | **+19.2%** | json-coeffs | Reconstructed agent's V2 per-platform ladder: psi_v2 = g*(psi_v0 - b) with (b,g) |
| **angleC-m3-agent-02** | `angle-C/module-3` | ok | 0.014740 | 0.011924 | **+19.1%** | json-coeffs | V3 per-platform (gain g + post-gain bias b3) refit using agent's run_variants.py |
| **angleC-m3-agent-03** | `angle-C/module-3` | ok | 0.014740 | 0.012248 | **+16.9%** | json-coeffs | Reconstructed V2 (per-platform gain): pred_v2 = a + b*(pred - bias), with (bias, |
| **angleC-m3-agent-04** | `angle-C/module-3` | ok | 0.014740 | 0.012808 | **+13.1%** | re-ran-script | Picked V3 per-platform steering gain k as the agent's 'favourite' because their  |
| **angleC-m3-agent-05** | `angle-C/module-3` | ok | 0.014740 | 0.011572 | **+21.5%** | json-coeffs | Per-platform coefficients: Mach-E (b=2.271627e-04, k=1.068590, tau=0.08), F-150  |
| **angleC-m4-agent-01** | `angle-C/module-4` | ok | 0.014740 | 0.011920 | **+19.1%** | json-coeffs | Agent shipped per-platform coefficients (PARAM_BY_PLATFORM); both Ford platforms |
| **angleC-m4-agent-02** | `angle-C/module-4` | ok | 0.014740 | 0.028573 | **-93.8%** | json-coeffs | Agent fitted L_eff=2.793 and bias on FORD_MUSTANG_MACH_E_MK1 only; canonical eva |
| **angleC-m4-agent-03** | `angle-C/module-4` | ok | 0.014740 | 0.011718 | **+20.5%** | json-coeffs | V3 lag rolls predictions by +1 sample per segment, invalidating the first sample |
| **angleC-m4-agent-04** | `angle-C/module-4` | ok | 0.014740 | 0.012159 | **+17.5%** | json-coeffs | Agent's headline was per-platform on a 4:1 interleaved TEST split; canonical eva |
| **angleC-m4-agent-05** | `angle-C/module-4` | ok | 0.014740 | 0.011545 | **+21.7%** | json-coeffs | Favourite model = agent's V3 (per-platform additive ladder: bias b, steering-gai |
| **angleD-m2-agent-01** | `angle-D/module-2` | ok | 0.014740 | 0.023600 | **-60.1%** | json-coeffs | Baseline recomputed from sim.csv yaw_rate_pred_rads matches the canonical baseli |
| **angleD-m2-agent-02** | `angle-D/module-2` | ok | 0.014740 | 0.013132 | **+10.9%** | imported-function | V1 applies per-segment straight-line yaw-gyro bias (mean of pred-meas where |del |
| **angleD-m2-agent-03** | `angle-D/module-2` | ok | 0.014740 | 0.013132 | **+10.9%** | json-coeffs | V1 declared best in REPORT.md table: 'V1 — KS w/ canonical L + per-segment yaw-g |
| **angleD-m2-agent-04** | `angle-D/module-2` | ok | 0.014740 | 0.011377 | **+22.8%** | imported-function | V2 declared agent's favourite in REPORT.md (V3/V4 regressed). Per-platform openp |
| **angleD-m2-agent-05** | `angle-D/module-2` | ok | 0.014740 | 0.010178 | **+31.0%** | imported-function | Reconstructed V4 = V3 (linear-ST with multi-start fit C_alpha per platform, per- |
| **angleD-m3-agent-01** | `angle-D/module-3` | ok | 0.014740 | 0.013132 | **+10.9%** | json-coeffs | Reconstructed V1 = (v/L)*tan(delta) - per_segment_bias, with bias = mean of (ks_ |
| **angleD-m3-agent-02** | `angle-D/module-3` | ok | 0.014740 | 0.018937 | **-28.5%** | imported-function | Agent only fit/declared V2 with Mach-E params; canonical eval pools across both  |
| **angleD-m3-agent-03** | `angle-D/module-3` | ok | 0.014740 | 0.011572 | **+21.5%** | imported-function | V2 prior C_alpha values are platform-specific; for FORD_MUSTANG_MACH_E_MK1 used  |
| **angleD-m3-agent-04** | `angle-D/module-3` | ok | 0.014740 | 0.014721 | **+0.1%** | json-coeffs | V4 = V3 (Linear single-track, fit C_alpha) with per-segment yaw-gyro bias (|delt |
| **angleD-m3-agent-05** | `angle-D/module-3` | ok | 0.014740 | 0.013132 | **+10.9%** | imported-function | V1 = KS + per-segment yaw-gyro bias on straights, as defined in agent's tools/ru |
| **angleD-m4-agent-01** | `angle-D/module-4` | ok | 0.014740 | 0.023600 | **-60.1%** | json-coeffs | Agent V1 procedure (KS + per-segment straight-line bias removal) is platform-agn |
| **angleD-m4-agent-02** | `angle-D/module-4` | ok | 0.014740 | 0.011377 | **+22.8%** | imported-function | V2 is the shipped best variant per REPORT.md ("V2 (Linear single-track with prio |
| **angleD-m4-agent-03** | `angle-D/module-4` | ok | 0.014740 | 0.013132 | **+10.9%** | json-coeffs | Agent shipped V1 on Mach-E only; applied here to both Mach-E and F-150 Lightning |
| **angleD-m4-agent-04** | `angle-D/module-4` | ok | 0.014740 | 0.013132 | **+10.9%** | json-coeffs | V1 = KS recalibrated (canonical L per platform: Mach-E 2.984 m, F-150 Lightning  |
| **angleD-m4-agent-05** | `angle-D/module-4` | ok | 0.014740 | 0.011377 | **+22.8%** | imported-function | V2 reconstructed by importing PARAM_BY_PLATFORM and re-implementing the two-line |
| **angleE-m2-agent-01** | `angle-E/module-2` | ok | 0.014740 | 0.013132 | **+10.9%** | imported-function | V1 reconstructed verbatim from tools/step4_run_st_upgrade.py: ks_pred=(v/L)*tan( |
| **angleE-m2-agent-02** | `angle-E/module-2` | ok | 0.014740 | 0.013132 | **+10.9%** | json-coeffs | Reconstructed V1 = KS pred (v/L · tan δ) minus per-segment straight-regime yaw b |
| **angleE-m2-agent-03** | `angle-E/module-2` | ok | 0.014740 | 0.013132 | **+10.9%** | json-coeffs | Reconstructed V1 = KS pred (v/L · tan δ) minus per-segment straight-regime yaw b |
| **angleE-m2-agent-04** | `angle-E/module-2` | ok | 0.014740 | 0.012628 | **+14.3%** | imported-function | V1 is KS (v/L)*tan(delta) minus a per-segment constant equal to the mean (ks_pre |
| **angleE-m2-agent-05** | `angle-E/module-2` | ok | 0.014740 | 0.013132 | **+10.9%** | json-coeffs | Agent declares V1 favourite by elimination: V2/V3 regress past V0, V1 alone impr |
| **angleE-m3-agent-01** | `angle-E/module-3` | ok | 0.014740 | 0.013132 | **+10.9%** | imported-function | V1 = platform-L KS yaw rate minus per-segment straight-regime bias (|delta|<0.01 |
| **angleE-m3-agent-02** | `angle-E/module-3` | ok | 0.014740 | 0.013132 | **+10.9%** | json-coeffs | V1 = KS yaw-rate (v/L * tan(delta_road)) with per-sim.csv-segment bias removal ( |
| **angleE-m3-agent-03** | `angle-E/module-3` | ok | 0.014740 | 0.013132 | **+10.9%** | imported-function | Favourite = V1 — only variant the agent reports as an improvement over V0 (Mach- |
| **angleE-m3-agent-04** | `angle-E/module-3` | ok | 0.014740 | 0.013132 | **+10.9%** | imported-function | Agent declared V1 their best variant ('the only improving step'; 'all of which i |
| **angleE-m3-agent-05** | `angle-E/module-3` | ok | 0.014740 | 0.013132 | **+10.9%** | imported-function | V1 is parameter-free apart from wheelbase L (2.984 m Mach-E, 3.700 m F-150 Light |
| **angleE-m4-agent-01** | `angle-E/module-4` | ok | 0.014740 | 0.013132 | **+10.9%** | imported-function | V1 = KS recalibrated with per-segment yaw-gyro bias subtracted; bias = mean(pred |
| **angleE-m4-agent-02** | `angle-E/module-4` | ok | 0.014740 | 0.013132 | **+10.9%** | other | Agent saved no coefficients/scripts under tools/ or out/; their REPORT names V1  |
| **angleE-m4-agent-03** | `angle-E/module-4` | ok | 0.014740 | 0.013132 | **+10.9%** | imported-function | Agent's REPORT scopes V1 to FORD_MUSTANG_MACH_E_MK1 only; canonical pooling appl |
| **angleE-m4-agent-04** | `angle-E/module-4` | ok | 0.014740 | 0.013132 | **+10.9%** | imported-function | Agent's REPORT names V1 as best ('Best variant overall: V1 (Δ vs V0 = 0.001434 r |
| **angleE-m4-agent-05** | `angle-E/module-4` | ok | 0.014740 | 0.013132 | **+10.9%** | imported-function | Agent labels V1 (`0.01469`, bolded) as best in their variant ladder; V2/V3 regre |
| **raw-agent-01** | `raw` | ok | 0.014740 | 0.019064 | **-29.3%** | json-coeffs | Agent's model hardcoded Tesla Model 3 wheelbase L=2.875m; applied AS-IS to Ford  |
| **raw-agent-02** | `raw` | ok | 0.014740 | 0.010951 | **+25.7%** | json-coeffs | Reconstructed B3 (per-platform tuned ladder) from out/results.json: yr = (v/L)*t |
| **raw-agent-03** | `raw` | ok | 0.014740 | 0.010713 | **+27.3%** | json-coeffs | Coefficients are platform-specific (Mach-E vs F-150 Lightning); applied each per |
| **raw-agent-04** | `raw` | ok | 0.014740 | 0.011961 | **+18.9%** | imported-function | V4 = (v / (L*(1+K_us*v^2))) * tan(delta_lag(tau) - b); fit on per-segment 50/50  |
| **raw-agent-05** | `raw` | ok | 0.014740 | 0.010006 | **+32.1%** | imported-function | V6 (full ladder) reconstructed end-to-end on canonical data: per-platform K_us r |
| **raw-agent-06** | `raw` | ok | 0.014740 | 0.010599 | **+28.1%** | imported-function | Reconstructed v4 (final ladder rung) from tools/score.py: per-segment bias subtr |
| **raw-agent-07** | `raw` | ok | 0.014740 | 0.007493 | **+49.2%** | json-coeffs | Agent's V1 per-segment bias was re-fit on each canonical segment (their original |
| **raw-agent-08** | `raw` | ok | 0.014740 | 0.008587 | **+41.7%** | re-ran-script | Reconstructed by re-running agent's V4 joint-fit + V5 lag-shift procedure on age |
| **raw-agent-09** | `raw` | ok | 0.014740 | 0.008837 | **+40.0%** | json-coeffs | Globbed all 545 canonical Ford sim.csv files; used 521. Baseline recomputation m |
| **raw-agent-10** | `raw` | ok | 0.014740 | 0.010258 | **+30.4%** | json-coeffs | V4 favourite: per-platform (offset, lag, scale, K_us) read from out/fits.json; p |


## Rubric pass rate (per item)

| rubric item | pass | fail | null | pass rate |
|---|---|---|---|---|
| `truth-channel-correct` | 83 | 1 | 1 | 83/84 = 99% |
| `contract-acknowledged` | 79 | 5 | 1 | 79/84 = 94% |
| `regime-breakdown-present` | 75 | 10 | 0 | 75/85 = 88% |
| `methodology-consistent` | 85 | 0 | 0 | 85/85 = 100% |
| `attribution-coherent` | 85 | 0 | 0 | 85/85 = 100% |
| `honest-regression-flagged` | 77 | 2 | 6 | 77/79 = 97% |

## Headline numbers (verbatim from each agent — NOT normalised)

| agent | platform | primary metric | baseline | final | improvement | top contributor |
|---|---|---|---|---|---|---|
| **angleA-m2-agent-01** | Ford (Mach-E MK1 + F-150 Lightning MK1), 545 segments total | Overall yaw-rate RMSE | 0.01804 rad/s (V0) | 0.01568 rad/s (V4) | 13.1% reduction | V4 understeer |
| **angleA-m2-agent-02** | FORD_MUSTANG_MACH_E_MK1 | RMSE on `yaw_rate_pred − yaw_rate_meas`, rad/s | 0.01550 | 0.01313 | 15.3% reduction | V1_seg_bias |
| **angleA-m2-agent-03** | FORD_MUSTANG_MACH_E_MK1 | pooled-sample RMSE on `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (rad/s) | 0.01613 | 0.01380 | 14.5% drop | V1 (bias removal) |
| **angleA-m2-agent-04** | `FORD_MUSTANG_MACH_E_MK1` (Ford Mach-E MK1, 315 segments, 913,626 samples @ 50 Hz) | RMSE of `yaw_rate_resid_rads = yaw_rate_pred − yaw_rate_meas` (rad/s) | 0.01613 | 0.01077 | total drop = 33.2% overall (V0 0.01613 → V4 0.01077) | V3_perseg_gain_fit |
| **angleA-m2-agent-05** | FORD_MUSTANG_MACH_E_MK1 | lateral residual `yaw_rate_pred − yaw_rate_meas` | V0 = 0.01613 | V4 = 0.01035 | 35.8% reduction | V2 + α re-fit |
| **angleA-m3-agent-01** | FORD_MUSTANG_MACH_E_MK1 | RMSE on `yaw_rate_resid_rads` (rad/s) | 0.01190 | 0.01003 | 15.7% improvement vs V0 | V4 Ridge residual learner on V3, LOSO |
| **angleA-m3-agent-02** | FORD_MUSTANG_MACH_E_MK1 | RMSE(yaw_rate_pred − yaw_rate_meas) | 0.01613 | 0.01469 | -0.00143 | V1 — KS recalibrated + per-segment straight-line yaw-gyro bias |
| **angleA-m3-agent-03** | FORD_MUSTANG_MACH_E_MK1 | lateral yaw-rate RMSE | V0 = 0.01613 | V1 = 0.01469 rad/s | 8.9% reduction | V1 KS recalibrated (canonical L) + per-segment yaw-gyro bias on straights |
| **angleA-m3-agent-04** | FORD_MUSTANG_MACH_E_MK1 | RMSE on `yaw_rate_resid_rads`, rad/s | 0.012144 | 0.010045 | 0.002099 rad/s (17.3% relative) | V4 Ridge residual learner on V3 (LOO CV) |
| **angleA-m3-agent-05** | FORD_MUSTANG_MACH_E_MK1 | RMSE of yaw-rate residual, rad/s | 0.01190 | 0.00963 | total drop = 19% relative (0.00227 rad/s absolute) | V4 Residual learner on V3 (LOO) |
| **angleA-m4-agent-01** | FORD_MUSTANG_MACH_E_MK1 | RMSE overall (rad/s) | 0.01394 | 0.01120 | −19.6% | V4 |
| **angleA-m4-agent-02** | FORD_MUSTANG_MACH_E_MK1 | RMSE overall (rad/s) | 0.012144 | 0.009608 | ~21% overall reduction; ~60% reduction on the straight regime | V4 |
| **angleA-m4-agent-03** | FORD_MUSTANG_MACH_E_MK1 | Overall yaw-rate RMSE | V0 = 0.016127 rad/s | V4 = 0.014897 rad/s | 7.6% relative improvement | V1 |
| **angleA-m4-agent-04** | FORD_MUSTANG_MACH_E_MK1 | Overall RMSE (rad/s) | 0.01214 | 0.01005 | 0.00210 rad/s (17.3% reduction) | V4 — Ridge residual learner on V3, LOSO CV |
| **angleA-m4-agent-05** | FORD_MUSTANG_MACH_E_MK1 | RMSE overall (rad/s) | 0.02570 | 0.02463 | V0→V3 total RMSE drop = **0.00064 rad/s** (2.5% reduction). Largest single improvement comes from **V1 alone** (0.00107 rad/s, 4.1%) | V1 |
| **angleB-m2-agent-01** | Ford Mustang Mach-E MK1 and Ford F-150 Lightning MK1 | RMSE in mrad/s | 15.84 | 7.92 | -50.0% vs V0 | V3 |
| **angleB-m2-agent-02** | `FORD_MUSTANG_MACH_E_MK1`, 80 segments (first 80 alphabetically), pre-generated `sim.csv`. | Yaw-rate RMSE 0.01190 → 0.00864 rad/s (-27.4%) across 80-segment Mach-E set, mask locked. | 0.01190 | 0.00864 | -27.4% | steering-lag (V3, 0.0022 rad/s) |
| **angleB-m2-agent-03** | FORD_MUSTANG_MACH_E_MK1 | RMSE of `yaw_rate_resid_rads = ψ̇_pred − ψ̇_meas`, broken out by regime, in **mrad/s** | 16.127 | 14.202 | 1.924 mrad/s (11.9%) | V1 |
| **angleB-m2-agent-04** | FORD_MUSTANG_MACH_E_MK1 | Lateral yaw-rate RMSE on FORD_MUSTANG_MACH_E_MK1 | 0.01613 | 0.01388 | -14.0% | V1 per-segment yaw-rate bias removal |
| **angleB-m2-agent-05** | FORD_MUSTANG_MACH_E_MK1 | RMSE of `yaw_rate_resid_rads` (rad/s) | 0.01161 | 0.00714 | Total V0 → V3 drop = 0.00447 rad/s (38% of V0) | V1 (+ per-segment yaw-rate bias removal) |
| **angleB-m3-agent-01** | FORD_MUSTANG_MACH_E_MK1 | RMSE of `pred − meas` over 315 segments / 913 626 samples at 50 Hz | 0.01613 | 0.01530 | V0→V4 drop = 0.0008 rad/s (~5%) | V1 KS + per-seg straight-line bias |
| **angleB-m3-agent-02** | FORD_MUSTANG_MACH_E_MK1 | Yaw-rate RMSE (rad/s), same segments, same regime mask | 0.0161 | 0.0149 | 0.0012 rad/s (7.5%) | V1 + per-seg straight-line yaw bias removal |
| **angleB-m3-agent-03** | FORD_MUSTANG_MACH_E_MK1 | RMSE of `ψ̇_pred − ψ̇_meas` in rad/s | 0.01550 | 0.01251 | -0.00299 | V4 — V3 + Ridge residual LOSO on [v, |a_y|, |δ|, sign(δ̇)] |
| **angleB-m3-agent-04** | FORD_MUSTANG_MACH_E_MK1 | RMSE of yaw-rate residual, rad/s | 0.01326 | 0.01098 | -17% | V1 KS + per-segment bias from straights |
| **angleB-m3-agent-05** | FORD_MUSTANG_MACH_E_MK1 | RMSE of `yaw_rate_pred − yaw_rate_meas_rads` | 0.01316 | 0.01166 | Total drop V0→V3 = -0.00150 rad/s (≈11% of V0) | V1 + per-segment straight-line bias (IMU gyro offset) |
| **angleB-m4-agent-01** | Ford Mustang Mach-E MK1 | yaw-rate RMSE (rad/s) | 0.01214 | 0.01055 | -13% overall RMSE (0.01214 → 0.01055 rad/s) | V1 per-segment IMU yaw-gyro bias removal |
| **angleB-m4-agent-02** | FORD_MUSTANG_MACH_E_MK1 | all-regime RMSE | 0.01613 | 0.01515 | Total drop V0→V3 = -0.000972 | V1 + per-segment straight-line bias |
| **angleB-m4-agent-03** | FORD_MUSTANG_MACH_E_MK1 | overall yaw-rate-residual RMSE | 0.01451 | 0.01262 | -13% | V1 IMU yaw-gyro bias / seg |
| **angleB-m4-agent-04** | FORD_MUSTANG_MACH_E_MK1 (315 segments, 913 626 samples, 50 Hz, clamped `v` + `δ`; predicting `yaw_rate_pred_rads` against `yaw_rate_meas_rads`) | overall yaw-rate-residual RMSE | 0.01613 | 0.01533 rad/s | -4.96% | V2 Linear ST steady-state, prior C_α |
| **angleB-m4-agent-05** | FORD_MUSTANG_MACH_E_MK1 | overall RMSE 0.01190 → 0.01013 rad/s (-15%) | 0.01190 | 0.01656 | Net V0→V4 is a regression | V1 per-seg bias |
| **angleC-m2-agent-01** | FORD_MUSTANG_MACH_E_MK1 | Yaw-rate RMSE | 0.924 | 0.892 | 3.5% reduction | V2 steering-gain k |
| **angleC-m2-agent-02** | FORD_MUSTANG_MACH_E_MK1 | Mach-E lateral RMSE | 16.13 | 15.53 | ~3.7% | V2 gain |
| **angleC-m2-agent-03** | FORD_MUSTANG_MACH_E_MK1 | lateral-yaw-rate ladder RMSE | 0.924 deg/s (V0) | 0.879 deg/s (V3) | 4.9% global cut | V3 + steering-gain k=1.0848 (per-platform LS, cornering-train) |
| **angleC-m2-agent-04** | FORD_MUSTANG_MACH_E_MK1 | RMSE in deg/s | 1.013 | 0.848 | -16.3% overall | V4 per-segment bias (-10.7%) |
| **angleC-m2-agent-05** | FORD_MUSTANG_MACH_E_MK1 | test-only RMSE of yaw-rate residual (rad/s) | 0.01613 | 0.01561 | V2 alone delivers +3.3% net | V2 steer-gain k = 1.0843 |
| **angleC-m3-agent-01** | F-150 Lightning | overall test-set RMSE | 0.02037 | 0.01636 | 19.7% | V2 +bias+gain |
| **angleC-m3-agent-02** | FORD_MUSTANG_MACH_E_MK1 and FORD_F_150_LIGHTNING_MK1 | test-set RMSE, rad/s | Mach-E overall RMSE 0.01613; Lightning 0.02037 | Mach-E 0.01567; Lightning 0.01638 | Mach-E -2.9%; Lightning -19.6% | V2 ×gain |
| **angleC-m3-agent-03** | FORD_MUSTANG_MACH_E_MK1 (315 seg / 913 626 samples) and FORD_F_150_LIGHTNING_MK1 (230 seg / 667 141 samples) | overall RMSE rad/s | 0.02037 | 0.01643 | dropping overall by 19.3% | V2 +gain (per-platform) |
| **angleC-m3-agent-04** | Mach-E (segment-bias variant) and Lightning (per-platform affine variant) | Lateral yaw-rate RMSE | 0.02037 | 0.01654 | 18.8% on Lightning | V3 steering gain k=0.892 |
| **angleC-m3-agent-05** | FORD_MUSTANG_MACH_E_MK1 (primary, 315 segs / 913 626 samp) and FORD_F_150_LIGHTNING_MK1 (230 segs / 667 141 samp) | yaw-rate test RMSE (rad/s) | 0.01613 | 0.01534 | -4.9% | V2 +gain `k=1.069` |
| **angleC-m4-agent-01** | Mustang Mach-E and **19.0% on F-150 Lightning** | held-out RMSE | V0=0.02037 | V3=0.01651 | 19.0% on F-150 Lightning | V2 +gain=0.859 |
| **angleC-m4-agent-02** | FORD_MUSTANG_MACH_E_MK1 (Mustang Mach-E MK1, 315 segments, 913 626 samples; test fold 182 725 via interleaved every-5th split) | overall yaw-rate RMSE | 0.01613 | 0.01557 | -3.5% overall, **-10% on transient cornering**, -6% on steady | V3 L_eff fit (L_eff=2.793 m) |
| **angleC-m4-agent-03** | F-150 Lightning | held-out test RMSE | 0.02037 | 0.01499 rad/s | -26% | V2 |
| **angleC-m4-agent-04** | FORD_MUSTANG_MACH_E_MK1 and FORD_F_150_LIGHTNING_MK1 | TEST RMSE | 0.01613 (Mustang); 0.02037 (F-150) | 0.01585 (Mustang); 0.01662 (F-150) | +1.7% on FORD_MUSTANG_MACH_E_MK1 (0.01613 → 0.01585 rad/s) and +18.4% on FORD_F_150_LIGHTNING_MK1 (0.02037 → 0.01662 rad/s) | per-platform steering-gain calibration (V3) |
| **angleC-m4-agent-05** | FORD_MUSTANG_MACH_E_MK1 (315 segments / 913 626 samples), FORD_F_150_LIGHTNING_MK1 (230 / 667 141) | ψ̇ residual recomputed as `pred − meas` | Mach-E V0 0.01613; F-150 V0 0.02037 | Mach-E V4 0.01323; F-150 V4 0.01488 | Mach-E 0.01613→0.01323; F-150 0.02037→0.01488 | V4 per-seg bias (cal) |
| **angleD-m2-agent-01** | FORD_MUSTANG_MACH_E_MK1 (Mach-E MK1) | overall RMSE [rad/s] | 0.01192 | 0.00993 | −0.00199 (−16.7%) | V1 KS recalibrated, canonical L, per-segment straight bias |
| **angleD-m2-agent-02** | Ford Mustang Mach-E (MK1) | Overall yaw-rate RMSE | 0.01178 rad/s (V0) | 0.00909 rad/s (V1) | 22.8% reduction | V1 KS recalib + per-segment gyro bias |
| **angleD-m2-agent-03** | FORD_MUSTANG_MACH_E_MK1 | Overall RMSE (rad/s) | 0.01277 | 0.01133 | −0.00144 (−11.3%) | V1 — KS w/ canonical `L` + per-segment yaw-gyro bias on straights |
| **angleD-m2-agent-04** | Ford Mustang Mach-E (MK1) | RMSE of yaw-rate residual (rad/s) | 0.01403 | 0.00825 | Δ overall RMSE = −0.00578 rad/s, −41% | V1 KS recalibrated + per-segment yaw-gyro bias |
| **angleD-m2-agent-05** | `FORD_MUSTANG_MACH_E_MK1` (Mach-E) | RMSE of `(ψ̇_pred − ψ̇_meas)` in rad/s | 0.01575 | 0.01499 | −4.8% RMSE | V1  KS recal (`L=2.875`) + per-seg straight-line bias |
| **angleD-m3-agent-01** | Ford Mustang Mach-E MK1 (`FORD_MUSTANG_MACH_E_MK1`), 30 of 315 available `sim.csv` segments, 86,964 rows total. | yaw-rate RMSE, rad/s | 0.01563 | 0.01381 | −0.00182 (improvement) | V1 |
| **angleD-m3-agent-02** | FORD_MUSTANG_MACH_E_MK1 | RMSE of yaw-rate residual, rad/s | 0.01143 | 0.00821 | −0.00288 rad/s total V0→V4 drop; V2 best at 0.00821 vs V0 0.01143 | V1 — KS recalibrated + per-segment straight-line gyro bias |
| **angleD-m3-agent-03** | FORD_MUSTANG_MACH_E_MK1 | Overall yaw-rate residual **RMSE 0.01403 → 0.00840 rad/s** | 0.01403 | 0.00840 | 40.1 % drop | V1  KS recalibrated (canonical `L`, per-seg yaw-gyro bias on straights) |
| **angleD-m3-agent-04** | FORD_MUSTANG_MACH_E_MK1 | Overall RMSE | 0.01214 | 0.01005 | Net honest gain over V0 is 0.00210 rad/s (~17%) | V4  Ridge residual learner on V3 (LOO out-of-fold) |
| **angleD-m3-agent-05** | FORD_MUSTANG_MACH_E_MK1 | RMSE in rad/s, lower is better | 0.01575 | 0.01368 | −39.5% | V1 KS + per-seg yaw-gyro bias |
| **angleD-m4-agent-01** | FORD_MUSTANG_MACH_E_MK1 | Overall RMSE (rad/s) | RMSE(V0) = 0.01082 | RMSE(V1) = 0.00885 | an 18.2 % drop vs V0 | V1 — KS recalibrated + per-segment straight-line yaw-gyro de-bias |
| **angleD-m4-agent-02** | FORD_MUSTANG_MACH_E_MK1 | Lateral yaw-rate RMSE on 12 Ford Mustang Mach-E segments | V0 = 0.01403 rad/s | V2 = 0.00825 rad/s | 41 % reduction | V1 KS recal + yaw-bias |
| **angleD-m4-agent-03** | FORD_MUSTANG_MACH_E_MK1 | yaw_rate_pred − yaw_rate_meas | 17.96 | 15.24 | +15.2% | V1  KS recalibrated + per-segment gyro bias |
| **angleD-m4-agent-04** | FORD_MUSTANG_MACH_E_MK1 | Overall RMSE (rad/s) | 0.01704 | 0.01635 | −0.00069 rad/s overall, **−0.00433 in the straight regime** | V1 |
| **angleD-m4-agent-05** | FORD_MUSTANG_MACH_E_MK1 | RMSE in rad/s; lower is better | 0.01545 | 0.00911 | Marginals sum to 0.006241; total drop is 0.006241 | V1 KS recal `(v/L) tan δ` + per-segment yaw-gyro bias on straights |
| **angleE-m2-agent-01** | FORD_MUSTANG_MACH_E_MK1 | yaw_rate_resid_rads = yaw_rate_pred − yaw_rate_meas | 0.01613 | 0.01469 | −0.00144 rad/s (−8.9 %) | V1 (KS recalib L + per-segment straight-row yaw-gyro bias) |
| **angleE-m2-agent-02** | FORD_MUSTANG_MACH_E_MK1 | yaw_rate_resid_rads = yaw_rate_pred − yaw_rate_meas | 0.01613 | 0.01663 | +0.00050 | V1 (KS recalib + per-seg bias) |
| **angleE-m2-agent-03** | FORD_MUSTANG_MACH_E_MK1 | yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads | 0.01613 | 0.01469 | −8.9% | V1 (KS recalib + per-seg gyro bias) |
| **angleE-m2-agent-04** | FORD_MUSTANG_MACH_E_MK1 | Lateral residual `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` is the sole metric. | 0.01613 | 0.01469 | +0.00144 improvement (8.9% relative) | V1 (KS recalib + per-segment yaw-gyro bias) |
| **angleE-m2-agent-05** | FORD_MUSTANG_MACH_E_MK1 | overall RMSE (rad/s) | 0.01613 | 0.01663 | +0.00050 (regression V0→V3) | V1 (KS recalib + bias) |
| **angleE-m3-agent-01** | FORD_MUSTANG_MACH_E_MK1 | RMSE overall (rad/s) | 0.01612 | 0.01664 | −0.00051 = total drop V0→V3 | V1 |
| **angleE-m3-agent-02** | FORD_MUSTANG_MACH_E_MK1 | RMSE of yaw-rate residual, rad/s | 0.016127 | 0.016635 | Total drop V0→V3: **−0.000508 rad/s** (i.e. the ladder ends worse than it started). | V1  KS recalib + per-seg bias |
| **angleE-m3-agent-03** | FORD_MUSTANG_MACH_E_MK1 | RMSE of `yaw_rate_resid_rads`, rad/s | 0.01613 | 0.01628 | V0→V3 total drop = −0.000155 rad/s (regression) | V1 KS recalibrated + per-segment straight-line gyro-bias removed |
| **angleE-m3-agent-04** | FORD_MUSTANG_MACH_E_MK1 | RMSE(yaw_rate_pred_rads − yaw_rate_meas_rads) | 0.016127 | 0.016635 | −0.001434 rad/s overall RMSE (≈ −8.9%) | V1 KS recalibrated (canonical L + per-segment bias) |
| **angleE-m3-agent-05** | FORD_MUSTANG_MACH_E_MK1 | RMSE of `ψ̇_pred − ψ̇_meas`, rad/s | 0.01613 | 0.01469 | −8.9 % | V1 (KS recalibrated with per-segment straight-line gyro-bias subtraction) |
| **angleE-m4-agent-01** | FORD_MUSTANG_MACH_E_MK1 | yaw_rate_resid_rads | 0.01613 | 0.01469 | -0.00143 rad/s (-8.9%) | V1 — KS recalib + per-segment straight-line bias |
| **angleE-m4-agent-02** | FORD_MUSTANG_MACH_E_MK1 | RMSE(yaw_rate_resid_rads) | 0.01613 | 0.01663 | Total drop V0 → V3: −0.000508 rad/s (the ladder net-regresses) | V1 KS recalibrated (bias-subtracted) |
| **angleE-m4-agent-03** | FORD_MUSTANG_MACH_E_MK1 | RMSE(yaw_rate_resid_rads) | 0.01613 | 0.01663 rad/s | −0.0005, i.e. worse | V1 KS recalibrated + per-segment straight-line bias |
| **angleE-m4-agent-04** | FORD_MUSTANG_MACH_E_MK1 | RMSE(yaw_rate_resid_rads) | 0.016127 | 0.016635 | Total drop V0 → V3: **−0.00051 rad/s** (V3 is worse than V0). | V1 — KS, canonical `L`, per-segment straight-line bias removed |
| **angleE-m4-agent-05** | FORD_MUSTANG_MACH_E_MK1 | RMSE(yaw_rate_resid_rads) | 0.01613 | 0.01663 | −0.00051 rad/s | V1 |
| **raw-agent-01** | Tesla Model 3 | pooled yaw-rate RMSE (rad/s, reported in deg/s), on Tesla Model 3 segments, activity-masked (v ≥ 5 m/s **and** |ψ̇_truth| ≥ 2 deg/s; n ≈ 85 300 samples across 120 segments) | 2.763 deg/s | 2.547 deg/s | –0.215 deg/s, –7.8 % | C1 (effective steer-ratio α) |
| **raw-agent-02** | 522 Ford segments with moving-vehicle samples (~1.39 M rows; Mach-E + F-150 Lightning) | sample-weighted RMSE of yaw-rate prediction | Baseline RMSE: 18.25 mrad/s | Final RMSE (per-platform tuned ladder): 15.43 mrad/s | −15.5% relative | B2 understeer factor K |
| **raw-agent-03** | Ford platforms (Mustang Mach-E MK1 and F-150 Lightning MK1) | RMSE of yaw-rate prediction (rad/s), evaluated on a held-out 20 % segment-level test split, pooled across both Ford platforms (Mustang Mach-E MK1 and F-150 Lightning MK1) | 0.01270 rad/s | 0.00839 rad/s | 33.9 % | understeer (K_us) |
| **raw-agent-04** | 545 Ford segments (Mach-E + F-150 Lightning) | Yaw-rate RMS residual | 0.01804 rad/s (1.034 °/s) | 0.01191 rad/s (0.682 °/s) | 34% reduction in RMS yaw-rate residual | V1 hygiene |
| **raw-agent-05** | Ford (Mach-E + F-150 Lightning) | pooled RMSE of predicted yaw rate vs. measured yaw rate, across all 545 Ford segments (Mach-E + F-150 Lightning, ~1.58 M samples) | 0.01804 | 0.01466 | −18.7 % | v3 + steady-state understeer (canonical Caf/Car) |
| **raw-agent-06** | 520 Ford segments | yaw-rate RMSE across 520 Ford segments (1.36 M samples at 50 Hz), in-motion (v > 2 m/s) only | 0.01431 rad/s | 0.00999 rad/s | 30.2 % reduction | v2_understeer |
| **raw-agent-07** | 545 Ford segments / 1,580,767 samples at 50 Hz from both FORD_MUSTANG_MACH_E_MK1 and FORD_F_150_LIGHTNING_MK1 | RMS yaw-rate residual (deg/s) | 1.0336 | 0.7401 | 28.4 % reduction | V1 + per-seg δ-bias |
| **raw-agent-08** | Ford (F-150 Lightning + Mach-E); Tesla excluded | Pooled yaw-rate RMSE across all 545 Ford segments (1.58M samples) | 1.034 deg/s | 0.809 deg/s | Reduction: 0.225 deg/s = 21.7 % of baseline RMSE | V3 understeer |
| **raw-agent-09** | Ford segments (Mach-E + F-150 Lightning) | pooled yaw-rate RMSE over all 520 Ford segments (Mach-E + F-150 Lightning), masked to `v > 2 m/s` (1.36M samples) | 0.01474 rad/s | 0.00894 rad/s | −39.4% RMSE | V4 — understeer `K·v²` |
| **raw-agent-10** | all 545 Ford segments (both Mach-E and F-150 Lightning) | RMSE of predicted yaw rate vs measured Yaw_Data_FD1 truth across **all 545 Ford segments** (both Mach-E and F-150 Lightning), restricted to moving samples (v > 2 m/s, N = 1,364,925). | 0.01481 | 0.00985 | −45% vs raw baseline; −33% vs hygiene-clean baseline | V3→V4 (understeer K_us) |

## Cohort convergence

**platform**
- `FORD_MUSTANG_MACH_E_MK1` — 54/85
- `F-150 Lightning` — 2/85
- `FORD_MUSTANG_MACH_E_MK1 and FORD_F_150_LIGHTNING_MK1` — 2/85
- `Ford Mustang Mach-E (MK1)` — 2/85
- `Ford (Mach-E MK1 + F-150 Lightning MK1), 545 segments total` — 1/85
- ``FORD_MUSTANG_MACH_E_MK1` (Ford Mach-E MK1, 315 segments, 913,626 samples @ 50 Hz)` — 1/85
- `Ford Mustang Mach-E MK1 and Ford F-150 Lightning MK1` — 1/85
- ``FORD_MUSTANG_MACH_E_MK1`, 80 segments (first 80 alphabetically), pre-generated `sim.csv`.` — 1/85
- `Ford Mustang Mach-E MK1` — 1/85
- `FORD_MUSTANG_MACH_E_MK1 (315 segments, 913 626 samples, 50 Hz, clamped `v` + `δ`; predicting `yaw_rate_pred_rads` against `yaw_rate_meas_rads`)` — 1/85
- `FORD_MUSTANG_MACH_E_MK1 (315 seg / 913 626 samples) and FORD_F_150_LIGHTNING_MK1 (230 seg / 667 141 samples)` — 1/85
- `Mach-E (segment-bias variant) and Lightning (per-platform affine variant)` — 1/85
- `FORD_MUSTANG_MACH_E_MK1 (primary, 315 segs / 913 626 samp) and FORD_F_150_LIGHTNING_MK1 (230 segs / 667 141 samp)` — 1/85
- `Mustang Mach-E and **19.0% on F-150 Lightning**` — 1/85
- `FORD_MUSTANG_MACH_E_MK1 (Mustang Mach-E MK1, 315 segments, 913 626 samples; test fold 182 725 via interleaved every-5th split)` — 1/85
- `FORD_MUSTANG_MACH_E_MK1 (315 segments / 913 626 samples), FORD_F_150_LIGHTNING_MK1 (230 / 667 141)` — 1/85
- `FORD_MUSTANG_MACH_E_MK1 (Mach-E MK1)` — 1/85
- ``FORD_MUSTANG_MACH_E_MK1` (Mach-E)` — 1/85
- `Ford Mustang Mach-E MK1 (`FORD_MUSTANG_MACH_E_MK1`), 30 of 315 available `sim.csv` segments, 86,964 rows total.` — 1/85
- `Tesla Model 3` — 1/85
- `522 Ford segments with moving-vehicle samples (~1.39 M rows; Mach-E + F-150 Lightning)` — 1/85
- `Ford platforms (Mustang Mach-E MK1 and F-150 Lightning MK1)` — 1/85
- `545 Ford segments (Mach-E + F-150 Lightning)` — 1/85
- `Ford (Mach-E + F-150 Lightning)` — 1/85
- `520 Ford segments` — 1/85
- `545 Ford segments / 1,580,767 samples at 50 Hz from both FORD_MUSTANG_MACH_E_MK1 and FORD_F_150_LIGHTNING_MK1` — 1/85
- `Ford (F-150 Lightning + Mach-E); Tesla excluded` — 1/85
- `Ford segments (Mach-E + F-150 Lightning)` — 1/85
- `all 545 Ford segments (both Mach-E and F-150 Lightning)` — 1/85

**primary_metric**
- `RMSE of yaw-rate residual, rad/s` — 4/85
- `RMSE overall (rad/s)` — 4/85
- `Overall RMSE (rad/s)` — 4/85
- `RMSE(yaw_rate_resid_rads)` — 4/85
- `Overall yaw-rate RMSE` — 3/85
- `overall yaw-rate-residual RMSE` — 2/85
- `yaw_rate_resid_rads = yaw_rate_pred − yaw_rate_meas` — 2/85
- `RMSE on `yaw_rate_pred − yaw_rate_meas`, rad/s` — 1/85
- `pooled-sample RMSE on `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (rad/s)` — 1/85
- `RMSE of `yaw_rate_resid_rads = yaw_rate_pred − yaw_rate_meas` (rad/s)` — 1/85
- `lateral residual `yaw_rate_pred − yaw_rate_meas`` — 1/85
- `RMSE on `yaw_rate_resid_rads` (rad/s)` — 1/85
- `RMSE(yaw_rate_pred − yaw_rate_meas)` — 1/85
- `lateral yaw-rate RMSE` — 1/85
- `RMSE on `yaw_rate_resid_rads`, rad/s` — 1/85
- `RMSE in mrad/s` — 1/85
- `Yaw-rate RMSE 0.01190 → 0.00864 rad/s (-27.4%) across 80-segment Mach-E set, mask locked.` — 1/85
- `RMSE of `yaw_rate_resid_rads = ψ̇_pred − ψ̇_meas`, broken out by regime, in **mrad/s**` — 1/85
- `Lateral yaw-rate RMSE on FORD_MUSTANG_MACH_E_MK1` — 1/85
- `RMSE of `yaw_rate_resid_rads` (rad/s)` — 1/85
- `RMSE of `pred − meas` over 315 segments / 913 626 samples at 50 Hz` — 1/85
- `Yaw-rate RMSE (rad/s), same segments, same regime mask` — 1/85
- `RMSE of `ψ̇_pred − ψ̇_meas` in rad/s` — 1/85
- `RMSE of `yaw_rate_pred − yaw_rate_meas_rads`` — 1/85
- `yaw-rate RMSE (rad/s)` — 1/85
- `all-regime RMSE` — 1/85
- `overall RMSE 0.01190 → 0.01013 rad/s (-15%)` — 1/85
- `Yaw-rate RMSE` — 1/85
- `Mach-E lateral RMSE` — 1/85
- `lateral-yaw-rate ladder RMSE` — 1/85
- `RMSE in deg/s` — 1/85
- `test-only RMSE of yaw-rate residual (rad/s)` — 1/85
- `overall test-set RMSE` — 1/85
- `test-set RMSE, rad/s` — 1/85
- `overall RMSE rad/s` — 1/85
- `Lateral yaw-rate RMSE` — 1/85
- `yaw-rate test RMSE (rad/s)` — 1/85
- `held-out RMSE` — 1/85
- `overall yaw-rate RMSE` — 1/85
- `held-out test RMSE` — 1/85
- `TEST RMSE` — 1/85
- `ψ̇ residual recomputed as `pred − meas`` — 1/85
- `overall RMSE [rad/s]` — 1/85
- `RMSE of yaw-rate residual (rad/s)` — 1/85
- `RMSE of `(ψ̇_pred − ψ̇_meas)` in rad/s` — 1/85
- `yaw-rate RMSE, rad/s` — 1/85
- `Overall yaw-rate residual **RMSE 0.01403 → 0.00840 rad/s**` — 1/85
- `Overall RMSE` — 1/85
- `RMSE in rad/s, lower is better` — 1/85
- `Lateral yaw-rate RMSE on 12 Ford Mustang Mach-E segments` — 1/85
- `yaw_rate_pred − yaw_rate_meas` — 1/85
- `RMSE in rad/s; lower is better` — 1/85
- `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` — 1/85
- `Lateral residual `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` is the sole metric.` — 1/85
- `overall RMSE (rad/s)` — 1/85
- `RMSE of `yaw_rate_resid_rads`, rad/s` — 1/85
- `RMSE(yaw_rate_pred_rads − yaw_rate_meas_rads)` — 1/85
- `RMSE of `ψ̇_pred − ψ̇_meas`, rad/s` — 1/85
- `yaw_rate_resid_rads` — 1/85
- `pooled yaw-rate RMSE (rad/s, reported in deg/s), on Tesla Model 3 segments, activity-masked (v ≥ 5 m/s **and** |ψ̇_truth| ≥ 2 deg/s; n ≈ 85 300 samples across 120 segments)` — 1/85
- `sample-weighted RMSE of yaw-rate prediction` — 1/85
- `RMSE of yaw-rate prediction (rad/s), evaluated on a held-out 20 % segment-level test split, pooled across both Ford platforms (Mustang Mach-E MK1 and F-150 Lightning MK1)` — 1/85
- `Yaw-rate RMS residual` — 1/85
- `pooled RMSE of predicted yaw rate vs. measured yaw rate, across all 545 Ford segments (Mach-E + F-150 Lightning, ~1.58 M samples)` — 1/85
- `yaw-rate RMSE across 520 Ford segments (1.36 M samples at 50 Hz), in-motion (v > 2 m/s) only` — 1/85
- `RMS yaw-rate residual (deg/s)` — 1/85
- `Pooled yaw-rate RMSE across all 545 Ford segments (1.58M samples)` — 1/85
- `pooled yaw-rate RMSE over all 520 Ford segments (Mach-E + F-150 Lightning), masked to `v > 2 m/s` (1.36M samples)` — 1/85
- `RMSE of predicted yaw rate vs measured Yaw_Data_FD1 truth across **all 545 Ford segments** (both Mach-E and F-150 Lightning), restricted to moving samples (v > 2 m/s, N = 1,364,925).` — 1/85

**top_contributor**
- `V1` — 7/85
- `V4` — 2/85
- `V4 understeer` — 1/85
- `V1_seg_bias` — 1/85
- `V1 (bias removal)` — 1/85
- `V3_perseg_gain_fit` — 1/85
- `V2 + α re-fit` — 1/85
- `V4 Ridge residual learner on V3, LOSO` — 1/85
- `V1 — KS recalibrated + per-segment straight-line yaw-gyro bias` — 1/85
- `V1 KS recalibrated (canonical L) + per-segment yaw-gyro bias on straights` — 1/85
- `V4 Ridge residual learner on V3 (LOO CV)` — 1/85
- `V4 Residual learner on V3 (LOO)` — 1/85
- `V4 — Ridge residual learner on V3, LOSO CV` — 1/85
- `V3` — 1/85
- `steering-lag (V3, 0.0022 rad/s)` — 1/85
- `V1 per-segment yaw-rate bias removal` — 1/85
- `V1 (+ per-segment yaw-rate bias removal)` — 1/85
- `V1 KS + per-seg straight-line bias` — 1/85
- `V1 + per-seg straight-line yaw bias removal` — 1/85
- `V4 — V3 + Ridge residual LOSO on [v, |a_y|, |δ|, sign(δ̇)]` — 1/85
- `V1 KS + per-segment bias from straights` — 1/85
- `V1 + per-segment straight-line bias (IMU gyro offset)` — 1/85
- `V1 per-segment IMU yaw-gyro bias removal` — 1/85
- `V1 + per-segment straight-line bias` — 1/85
- `V1 IMU yaw-gyro bias / seg` — 1/85
- `V2 Linear ST steady-state, prior C_α` — 1/85
- `V1 per-seg bias` — 1/85
- `V2 steering-gain k` — 1/85
- `V2 gain` — 1/85
- `V3 + steering-gain k=1.0848 (per-platform LS, cornering-train)` — 1/85
- `V4 per-segment bias (-10.7%)` — 1/85
- `V2 steer-gain k = 1.0843` — 1/85
- `V2 +bias+gain` — 1/85
- `V2 ×gain` — 1/85
- `V2 +gain (per-platform)` — 1/85
- `V3 steering gain k=0.892` — 1/85
- `V2 +gain `k=1.069`` — 1/85
- `V2 +gain=0.859` — 1/85
- `V3 L_eff fit (L_eff=2.793 m)` — 1/85
- `V2` — 1/85
- `per-platform steering-gain calibration (V3)` — 1/85
- `V4 per-seg bias (cal)` — 1/85
- `V1 KS recalibrated, canonical L, per-segment straight bias` — 1/85
- `V1 KS recalib + per-segment gyro bias` — 1/85
- `V1 — KS w/ canonical `L` + per-segment yaw-gyro bias on straights` — 1/85
- `V1 KS recalibrated + per-segment yaw-gyro bias` — 1/85
- `V1  KS recal (`L=2.875`) + per-seg straight-line bias` — 1/85
- `V1 — KS recalibrated + per-segment straight-line gyro bias` — 1/85
- `V1  KS recalibrated (canonical `L`, per-seg yaw-gyro bias on straights)` — 1/85
- `V4  Ridge residual learner on V3 (LOO out-of-fold)` — 1/85
- `V1 KS + per-seg yaw-gyro bias` — 1/85
- `V1 — KS recalibrated + per-segment straight-line yaw-gyro de-bias` — 1/85
- `V1 KS recal + yaw-bias` — 1/85
- `V1  KS recalibrated + per-segment gyro bias` — 1/85
- `V1 KS recal `(v/L) tan δ` + per-segment yaw-gyro bias on straights` — 1/85
- `V1 (KS recalib L + per-segment straight-row yaw-gyro bias)` — 1/85
- `V1 (KS recalib + per-seg bias)` — 1/85
- `V1 (KS recalib + per-seg gyro bias)` — 1/85
- `V1 (KS recalib + per-segment yaw-gyro bias)` — 1/85
- `V1 (KS recalib + bias)` — 1/85
- `V1  KS recalib + per-seg bias` — 1/85
- `V1 KS recalibrated + per-segment straight-line gyro-bias removed` — 1/85
- `V1 KS recalibrated (canonical L + per-segment bias)` — 1/85
- `V1 (KS recalibrated with per-segment straight-line gyro-bias subtraction)` — 1/85
- `V1 — KS recalib + per-segment straight-line bias` — 1/85
- `V1 KS recalibrated (bias-subtracted)` — 1/85
- `V1 KS recalibrated + per-segment straight-line bias` — 1/85
- `V1 — KS, canonical `L`, per-segment straight-line bias removed` — 1/85
- `C1 (effective steer-ratio α)` — 1/85
- `B2 understeer factor K` — 1/85
- `understeer (K_us)` — 1/85
- `V1 hygiene` — 1/85
- `v3 + steady-state understeer (canonical Caf/Car)` — 1/85
- `v2_understeer` — 1/85
- `V1 + per-seg δ-bias` — 1/85
- `V3 understeer` — 1/85
- `V4 — understeer `K·v²`` — 1/85
- `V3→V4 (understeer K_us)` — 1/85

## Honesty flags

- declared limitations per agent: min=2, median=3, max=6
- named a data gap / missing truth channel: 54/85
- ⚠️ fabricated truth/proxy WITHOUT declaring it: 0/85

## Trap-trip hotspots (rubric items most agents missed)

- `regime-breakdown-present`: 10/85 agents failed
- `contract-acknowledged`: 5/85 agents failed
- `honest-regression-flagged`: 2/85 agents failed
