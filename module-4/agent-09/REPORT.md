# Module-4.v1.01 / agent-09 — REPORT

## Headline numerical result

Dev-set pooled (1996 segments, all 4 platforms):
- **yaw_rate_rmse = 0.005818 rad/s** (vs V0 baseline 0.012934, **-55.0%**)
- **cte_rmse = 56.98 m** (vs V0 baseline 163.83, **-65.2%**)

Per platform on dev: Lightning yaw=0.00565 cte=61.98; Mustang yaw=0.00839 cte=100.48; Hyundai yaw=0.00762 cte=69.12; Tesla 0/0 (V0 passthrough, no truth channel).

## What I implemented (variants explored under `out/`)

- **Variant A**: V1 + per-segment δ0 for Lightning → worse (low-yaw mask is biased on Lightning).
- **Variant B**: refit V1 (g, L, K_us, τ, δ0) per platform on 60-segment sample → ~+0.2% yaw, ~-1.6% cte.
- **Variant C**: same refit on **all** segments (175/240/800 per platform) → yaw=0.005822, cte=57.04.
- **Variant D (shipped)**: V1 with extra nonlinear understeer `K = K_us + K_us2·|δ_eff|` and full-data refit → yaw=0.005818, cte=56.98.

Final-model shipped at `final-model/predict.py` + `fit_coeffs.json` + `manifest.json`. Honors the 8-column operating contract (smoke-tested against `sim-only/`). Tesla falls through to V0 passthrough.

## Most painful missing harness component

A *cohort prior on V1's ceiling*. The references describe V1 as the rung-0 converged ceiling (m3 cohort showed it was hand-tuned to within "a basis point or two"). Nothing in the harness automatically told me "stop tuning V1 coeffs, move to a structurally different model" — I had to discover that experimentally by watching yaw improvements drop below 1% per variant. A `compare-models` automated "diminishing returns" alarm would have routed me to a dynamic-bicycle / tire-slip model 20 minutes earlier.

## Rule-prevented near-actions

I almost peeked at `_grade/` to see what other agents shipped and what scores got accepted; the isolation rules stopped me. I also wanted to copy from `module-3.v3/` for prior cohort patterns — same.

## Most surprising thing

V1 was already so close to the ceiling that refitting coefficients on the *full* dataset versus a 60-segment sample changed yaw by only ~0.4% and changed CTE in the *wrong direction* (+0.3%). The Mustang `K_us2 ≈ 0.0087` was the single non-trivial nonlinearity the refit found — all other K_us2 terms were near-zero. The marginal returns on V1's structural form are essentially exhausted; the next real lift needs a different model class (dynamic single-track with tire-slip + Iz).

## Failures

Variant A actively regressed Lightning (per-segment δ0 had too few low-yaw samples). Variant C regressed CTE slightly while improving yaw — typical two-KPI trade. Variants B, C, D all converged within ~1% of V1 on yaw, well within the "V1 ceiling" cohort prior.

## Isolation report

```
ISOLATION_REPORT:
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "All reads stayed under agent-09/, code/ symlink, and data/ symlink. Final REPORT.md content returned in-message because the subagent system prompt blocks Write on report.md."
```
