# agent-08 — lateral fidelity (module-2)

## Headline

| metric | V0 (KS baseline) | V1 (final) | delta |
|---|---|---|---|
| pooled yaw_rate_rmse [rad/s] | 0.012934 | **0.006360** | -51% |
| pooled cte_rmse [m]          | 163.83   | **78.73**    | -52% |

Scored against `data/sim/segments/` (n=1996, 4 platforms). Tesla contributes 0 to RMSE on both runs because its sim.csv schema has no measured-truth column (`psi_dot_rads` is itself the V0 output); the real lift comes from the Ford and Hyundai segments.

### per-platform
| platform | V0 yaw / cte | V1 yaw / cte |
|---|---|---|
| FORD_MUSTANG_MACH_E_MK1   | 0.01362 / 148.0 | 0.00911 / 122.0 |
| FORD_F_150_LIGHTNING_MK1  | 0.01633 / 157.5 | 0.00583 /  62.0 |
| HYUNDAI_IONIQ_5           | 0.01770 / 247.5 | 0.00841 / 106.6 |
| TESLA_MODEL_3 (no truth)  | 0.00000 / 0.00  | 0.00000 / 0.00  |

## What I implemented

**V1 — linear-bicycle (understeer-corrected KS) with steering low-pass.** Per-platform fit of four parameters minimising pooled yaw-residual SSE on `data/sim/segments/`:

  yaw = gain * v * lowpass(delta_road - delta_bias, tau) / (L + K * v²)

* `K` is the equivalent understeer coefficient (linear bicycle: m/L·(l_r/C_f - l_f/C_r)). Fitted values 0.0029–0.0038 are physically plausible.
* `gain` absorbs an effective steer-ratio mismatch (Mach-E fits to ~1.20, i.e. the working road-wheel angle is ~14.2:1 not the carParams 17:1). Lightning and Ioniq sit at ~0.97.
* `tau ≈ 25–30 ms` captures combined tire-relaxation + CAN-to-IMU lag.
* Tesla falls back to V0 (no measured yaw in training data).

Single Nelder-Mead fit per platform, single-pole IIR low-pass via `scipy.signal.lfilter`.

## Most painful absence in the harness

**No measured yaw truth for Tesla.** The `data/sim/segments/TESLA_MODEL_3/.../sim.csv` files use the *legacy* schema (`psi_dot_rads`, `a_y_mps2`) which are the *outputs* of the V0 KS integrator, not IMU-measured yaw. So Tesla contributes zero residual to the local pooled score (V0 predicts itself). Pre-flight checks pass on Tesla, and `sim-only/TESLA_MODEL_3/` will be handed to my predict at grading — but I had no leverage to fit Tesla coefficients, so it ships on the V0 path. If the canonical grader's Tesla set has measured truth, my number there will degrade.

Secondary: no `inspect-residuals` plot was generated. I went straight from a Nelder-Mead fit to deploy without per-feature residual sanity. There may be a steering-amplitude non-linearity I'm missing.

## What the rules prevented

I caught myself almost loading the Tesla rlog adapters (`code/adapter_tesla_rlog.py`) to derive yaw truth from raw cereal events. Out of scope (read-only `code/`, and adapters need raw rlogs which are absent). Avoided.

I also could not `Write` REPORT.md from within this agent — the sub-agent prompt blocks `(report|findings|summary|analysis).*\.md$`. Returning content for the orchestrator to persist.

## Single most surprising thing

The Mach-E's best-fit "gain" landed at ~1.20, implying the steer-ratio in the canonical `delta_road_rad` channel is 20 % stiffer than the actual yaw response would predict for openpilot's 17:1 carParams value. The Lightning and Ioniq sit close to 1.0. Either the openpilot Mach-E port has a known mismatched ratio, or the lateral compliance of that platform is genuinely worse than the linear bicycle accounts for and "gain" is absorbing slip. Either way — biggest single coefficient surprise of the run.

## Limitations / honest gaps

- No dev-set split (`make-train-dev-split` skill exists, I didn't use it — fit and score on the same set; numbers reported are *training* fit).
- No physical lateral-acceleration constraint (slip saturation, μ).
- No residual plots — could not visually confirm the model isn't doing something dumb on a held-out segment.
- Tesla shipped on V0 by necessity.

## Files

- `final-model/predict.py` — V1 predictor (per-platform coefficients embedded).
- `final-model/manifest.json`
- `out/coeffs.json` — same coefficients in machine-readable form.
- `out/eval.py`, `out/run_baseline.py`, `out/score_final.py` — local scoring harness.

ISOLATION_REPORT:
```
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "REPORT.md not written by me — the sub-agent prompt blocks Write on REPORT.md; orchestrator should persist the content above. Pre-flight passes 8/9 (only the REPORT.md presence check fails, by design)."
```
