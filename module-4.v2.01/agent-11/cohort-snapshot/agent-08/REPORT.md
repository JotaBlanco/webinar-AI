# REPORT — module-4.v2.01-agent-08

## 1. Headline numerical result

M4 (relaxation-length tire on V1 kinematic core), the orthogonal-rung candidate:
- **Dev:** yaw RMSE = **0.005631 rad/s**, CTE RMSE = **52.10 m**
- **Test (preflight --final):** yaw = **0.005760 rad/s**, CTE = **48.87 m**

V1 on the same splits: dev 0.005430 / 52.22, test 0.005556 / 48.98. M4 wins CTE by ~0.1 m and loses yaw by ~0.0002 — a wash. The 90-agent plateau holds. No structural climb.

| Split | V1 yaw | V1 cte | M4 yaw | M4 cte |
|---|---|---|---|---|
| Dev  | 0.005430 | 52.22 | 0.005631 | 52.10 |
| Test | 0.005556 | 48.98 | 0.005760 | 48.87 |

## 2. What I implemented

- **M4 relaxation-length** (shipped): one fitted σ per platform on the frozen train split via 1D grid (0.05–2.2). σ_F150 = σ_MachE = 0.4 m, σ_Hyundai = 0.3 m. Holds V1's per-platform g/L_eff/K_us/δ₀ fixed.
- **M1 linear-dynamic single-track** (shelved): Nelder-Mead fit converged on F150 (C_αf≈246k, C_αr≈470k, I_z≈15k) then OOM-killed mid-Mach-E with parallel sibling agents saturating CPU. Even partial-fit dev: yaw 0.0088 / cte 118 — worse than V1.

## 3. Most painful absence

A **vectorised batched-segment fitter**. The default `skills/fit-model` per-iteration loop re-reads CSVs and forward-integrates segment-by-segment in Python. For M1 at 1187 train segs × ~80 Nelder-Mead iters this was budget-killing under load. I had to hand-roll a per-platform array-cached sweep (`sweep_m4_fast.py`) to make M4 tractable; the dynamics ladder (M1–M3, M5) was effectively unreachable at this hardware ÷ wall-clock ratio.

## 4. What I almost did but rules prevented

Considered peeking at `module-4.v2/` cohort agents' shipped models to see what σ values converged there. Rules prevented; I held to grid search alone.

## 5. Single most surprising thing

Both F150 and Mach-E land on σ = 0.4 m (mid-grid) — not at zero (null result) or at 1.0 m (the V1 τ=0.06s × v≈15m/s ≈ 0.9 m equivalent). The physically-correct distance-domain lag is real but the time-domain τ is *already close enough* at the dataset's typical speed band that swapping formulations doesn't move the pooled needle.

## Harness friction

- Sub-agent Write blocked on `REPORT.md` pattern (as expected).
- **Sibling-agent visibility leak**: `ps aux` reveals other agents' running `fit.py` processes by full path, so the existence of parallel sibling work is observable even when filesystem reads are blocked. I observed only process names; did not read other agents' files. Worth noting as a side-channel for future isolation work.

---

ISOLATION_REPORT:
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "M1 fit run by another agent visible via ps aux; only observed process names, did not read other agents' files. Final-model bundle at final-model/ passes all preflight checks except test_split_gate which warns (data/sim/test/ glob path not seeded); test scoring done directly via FROZEN_SPLIT_ALLOW_TEST=1 env."
