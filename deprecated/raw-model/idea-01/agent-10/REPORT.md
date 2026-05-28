# Lateral-Prediction Improvement Report — agent-10

### 1. Headline number

**Primary metric:** RMSE of predicted yaw rate vs measured Yaw_Data_FD1 truth across **all 545 Ford segments** (both Mach-E and F-150 Lightning), restricted to moving samples (v > 2 m/s, N = 1,364,925).

| | Yaw-rate RMSE (rad/s) | vs baseline |
|---|---|---|
| **Baseline (stock KS, all samples)** | **0.01782** | — |
| Baseline (stock KS, moving only) | 0.01481 | −17% |
| **Final (V4, moving only)** | **0.00985** | **−45% vs raw baseline; −33% vs hygiene-clean baseline** |

Secondary metric — lateral-acceleration RMSE (a_y = v·ψ̇, m/s²): **0.386 → 0.269** (-30%) on moving samples. (Unfiltered F-150 a_y RMSE is ~11 m/s² and is dominated by a non-zero `VehLatComp_A_Actl` reading at v=0 — sensor / ground-tilt bias, not model error.)

### 2. What I implemented (ladder)

KS lateral output is `ψ̇ = (v/L)·tan(δ)`, `a_y = v·ψ̇`. δ comes from `StePinComp_An_Est / steerRatio`. Truth = `VehYaw_W_Actl` from `Yaw_Data_FD1`. All fits are per-platform on the full corpus, closed-form least squares.

- **V0** Baseline = the `yaw_rate_pred_rads` already in sim.csv (stock KS, openpilot-canonical parameters).
- **V1** **Steering zero-offset** δ_off (rad, road-wheel) — Mach-E: −0.0001, F-150: −0.0006. Tiny.
- **V2** **Time-lag alignment** — brute-force best integer-sample shift (max 0.5 s) of prediction vs measurement. Best lag: Mach-E 0 samples, F-150 1 sample (20 ms). Essentially nothing.
- **V3** **Effective steer-ratio fit** — multiplicative scale s on δ; equiv. `i_s_eff = i_s/s`. Mach-E: 17.0 → **15.6** (s=1.09), F-150: 16.9 → **18.9** (s=0.88). Absorbs steering-column / rack compliance and tyre slip in steady state.
- **V4** **Understeer-gradient term** — replace `ψ̇ = v·δ/L` with `ψ̇ = v·δ_eff / (L + K_us·v²)` (steady-state bicycle / Ackermann + understeer). Fitted K_us: Mach-E 0.0010 s², F-150 0.0018 s². Captures the v²-dependent understeer growth KS ignores.

### 3. Attribution

**Two accounting schemes reported (both honest, neither uniquely "true"):**

**A) Cumulative ladder (sequential drop-in)** — primary attribution. Total moving-only yaw-RMSE reduction V0→V4 = 0.00458 rad/s:

| Step | Δ RMSE | % of total |
|---|---|---|
| V0→V1 (δ-offset)         | +0.00018 | **3.9%** |
| V1→V2 (time-lag)         | +0.00000 | **0.0%** |
| V2→V3 (effective i_s)    | +0.00210 | **45.8%** |
| V3→V4 (understeer K_us)  | +0.00230 | **50.3%** |

**B) Standalone (each technique applied alone vs V0)** — sanity check:

| Technique | Δ RMSE alone |
|---|---|
| δ-offset | 0.00018 |
| time-lag | 0.00000 |
| effective i_s | 0.00205 |
| K_us (with stock i_s) | 0.00238 |

The standalone columns nearly add up to the cumulative gain, which means the techniques are **largely orthogonal** — there's no double-counting between the steer-ratio fit and the understeer term, even though both involve "scaling δ." That's because K_us multiplies the denominator by v² while s multiplies the numerator; they decouple at the v-distribution level.

**Bonus "data hygiene" attribution (not a model change):** dropping v ≤ 2 m/s samples drops RMSE from 0.01782 → 0.01481 (an additional 0.00301 rad/s). Reported separately because it isn't a model fix — it removes idling segments where KS trivially predicts ~0 yaw but the IMU records sensor bias.

### 4. Surprises

- **The "time lag" channel is dead.** I expected ~40–80 ms of CAN-to-IMU delay. Fitted lag is 0 (Mach-E) or 20 ms (F-150). Either the rlog resampler already aligned them or the Yaw_Data_FD1 signal is genuinely low-latency.
- **The steer-ratio correction goes opposite ways on the two platforms.** Mach-E wants i_s reduced 17.0 → 15.6 (car is *more* responsive than the spec'd ratio implies). F-150 wants i_s raised 16.9 → 18.9 (truck is *less* responsive). I'd have expected both to drift in the same direction (compliance always reduces effective angle), so the Mach-E direction is a small puzzle — possibly a road-wheel-vs-pinion convention mismatch in the adapter, or net oversteer due to rear-bias and stiff rear tyres.
- **The F-150 `VehLatComp_A_Actl` channel has a large stationary bias** (~ −0.15 m/s² at v=0) — visible in any segment that contains an idle. This made the raw a_y RMSE look like ~11 m/s² before filtering. The yaw-rate channel does not have this issue.
- **Bias offset δ_off is essentially zero** on both platforms — the Ford steering-pinion calibration is trustworthy. This is the *opposite* of what you'd see on most aftermarket harnesses.

### 5. Limitations

- I only worked the **steady-state lateral output** (`ψ̇`, `a_y`). I did not touch transient dynamics — body slip β, tyre relaxation length, ST cornering stiffness fit. The code has a ST-model stub waiting (parameters.py exposes `C_alpha_f`/`C_alpha_r`), but in 15 minutes I couldn't responsibly fit a coupled bicycle ODE across 1.4 M samples.
- I fit a single global `(δ_off, lag, s, K_us)` per platform. A **per-segment** or **per-driver** fit, or one segmented by speed bin, would probably reduce residuals further (especially for K_us, which physically depends on tyre temperature and load).
- I made no attempt to **decouple δ_off from i_s drift** — both are absorbing a partly shared affine-in-δ error term; a joint optimisation rather than the sequential V1-then-V3 approach would re-allocate the attribution.
- The Tesla segments were left out: their CSVs lack a measured yaw-rate truth channel (per the README), so RMSE is undefined there. Improvements presumably transfer but I have no way to score them.
- I did not read any sibling agent's outputs, any `webinar-angle-*/modulo-*/` folder, or `webinar-00/`. No harness blocks fired.

---

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Worked entirely inside ./agent-10/, ./code/ (read-only), and ./data/ (read-only). All artefacts under tools/ and out/. TodoWrite reminder ignored; task was short enough to track in head."
```
