"""Run V0..V4 on the same Mach-E sample set saved in out/baseline.npz."""
import os, json
import numpy as np
from scipy.optimize import minimize

NPZ = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-05/out/baseline.npz"
OUT = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-05/out"

d = np.load(NPZ)
seg     = d["seg"]
delta   = d["delta_road"]
v       = d["v"]
yaw_m   = d["yaw_meas"]
yaw_p   = d["yaw_pred"]      # V0 prediction = KS (v/L)·tan(δ)
resid0  = d["yaw_resid"]     # = yaw_p - yaw_m
straight  = d["straight"]
steady    = d["steady"]
transient = d["transient"]
ddelta_dt = d["ddelta_dt"]

# Mach-E ST params from skill doc (PARAM_BY_PLATFORM canonical):
L   = 2.984
m   = 2336.0
l_f = 1.313
l_r = 1.671
Cf0 = 286_551.0
Cr0 = 355_912.0

def rmse(x):
    x = np.asarray(x)
    x = x[np.isfinite(x)]
    return float(np.sqrt(np.mean(x ** 2))) if len(x) else float("nan")

def report(name, resid):
    return {
        "overall":   rmse(resid),
        "straight":  rmse(resid[straight]),
        "steady":    rmse(resid[steady]),
        "transient": rmse(resid[transient]),
        "N": int(np.isfinite(resid).sum()),
    }

results = {}
results["V0_baseline_KS"] = report("V0", resid0)

# ------------- V1: per-segment yaw-bias from straight-line samples -----------
# Bias is estimated as the *mean residual on straight-line samples within that segment*
# then subtracted from the residual everywhere in that segment.
bias_by_seg = {}
for s in np.unique(seg):
    msk = (seg == s) & straight
    if msk.sum() > 50:
        bias_by_seg[int(s)] = float(np.mean(resid0[msk]))
    else:
        bias_by_seg[int(s)] = 0.0
bias_vec = np.array([bias_by_seg[int(s)] for s in seg])
resid1 = resid0 - bias_vec
results["V1_per_seg_bias"] = report("V1", resid1)

# ------------- V2: linear ST steady-state gain, prior C_alpha ----------------
def linear_st_yaw(v_arr, delta_arr, Cf, Cr):
    """Steady-state ST: ψ̇ = v·δ / (L·(1 + K_us·v²)), KS fallback for v < v_min."""
    K_us = m * (l_r * Cr - l_f * Cf) / (L ** 2 * Cf * Cr)
    v_min = 2.0
    yaw = np.where(
        v_arr >= v_min,
        v_arr * delta_arr / (L * (1.0 + K_us * v_arr ** 2)),
        (v_arr / L) * np.tan(delta_arr),  # KS fallback
    )
    return yaw

yaw_v2 = linear_st_yaw(v, delta, Cf0, Cr0)
# V2 residual: still applies the V1 per-segment bias correction (cumulative ladder).
resid2 = (yaw_v2 - yaw_m) - bias_vec
results["V2_lin_ST_prior_Ca"] = report("V2", resid2)
K_us_prior = m * (l_r * Cr0 - l_f * Cf0) / (L ** 2 * Cf0 * Cr0)
print(f"V2: K_us(prior) = {K_us_prior:.5f} s²/m²  (positive => understeer)")

# ------------- V3: linear ST with fit C_alpha (bounded) ----------------------
# Fit C_f, C_r to minimise RMSE on cornering samples (steady+transient),
# bounded to [50, 500] kN/rad. We minimise on residual *after* V1 bias.
fit_mask = (steady | transient) & np.isfinite(v) & (v >= 2.0)
v_fit = v[fit_mask]
d_fit = delta[fit_mask]
ym_fit = yaw_m[fit_mask]
bias_fit = bias_vec[fit_mask]

def loss(theta):
    Cf, Cr = theta
    yhat = linear_st_yaw(v_fit, d_fit, Cf, Cr)
    r = (yhat - ym_fit) - bias_fit
    return float(np.mean(r ** 2))

from scipy.optimize import minimize
x0 = np.array([Cf0, Cr0])
bnds = [(50_000.0, 500_000.0), (50_000.0, 500_000.0)]
res = minimize(loss, x0, method="L-BFGS-B", bounds=bnds)
Cf_hat, Cr_hat = res.x
print(f"V3: fit C_f = {Cf_hat:,.0f}, C_r = {Cr_hat:,.0f}  (bounds 50k–500k)")
peg_f = abs(Cf_hat - 500_000.0) < 1.0 or abs(Cf_hat - 50_000.0) < 1.0
peg_r = abs(Cr_hat - 500_000.0) < 1.0 or abs(Cr_hat - 50_000.0) < 1.0
print(f"V3: pegged? front={peg_f}, rear={peg_r}")

yaw_v3 = linear_st_yaw(v, delta, Cf_hat, Cr_hat)
resid3 = (yaw_v3 - yaw_m) - bias_vec
results["V3_lin_ST_fit_Ca"] = report("V3", resid3)

# ------------- V4: steering-rate lead, tau on transient cornering -----------
def yaw_with_tau(tau):
    delta_eff = delta + tau * ddelta_dt
    return linear_st_yaw(v, delta_eff, Cf_hat, Cr_hat)

best = (None, np.inf)
for tau in np.linspace(0.0, 0.15, 31):
    y = yaw_with_tau(tau)
    r_trans = (y - yaw_m)[transient] - bias_vec[transient]
    val = rmse(r_trans)
    if val < best[1]:
        best = (tau, val)
tau_star, _ = best
print(f"V4: τ* = {tau_star:.3f} s  (search 0..0.15 s)")
yaw_v4 = yaw_with_tau(tau_star)
resid4 = (yaw_v4 - yaw_m) - bias_vec
results["V4_st_rate_lead"] = report("V4", resid4)

# ------------- Marginals ------------------------------------------------------
order = ["V0_baseline_KS", "V1_per_seg_bias", "V2_lin_ST_prior_Ca",
         "V3_lin_ST_fit_Ca", "V4_st_rate_lead"]
prev = None
print("\n=== Variant ladder (overall + per-regime RMSE [rad/s]) ===")
print(f"{'variant':<24} {'overall':>9} {'straight':>9} {'steady':>9} {'transient':>10} {'Δ_overall':>10}")
marginals = []
for k in order:
    r = results[k]
    if prev is None:
        d_over = 0.0
    else:
        d_over = prev - r["overall"]
    marginals.append((k, d_over))
    print(f"{k:<24} {r['overall']:>9.5f} {r['straight']:>9.5f} {r['steady']:>9.5f} {r['transient']:>10.5f} {d_over:>+10.5f}")
    prev = r["overall"]

total = results["V0_baseline_KS"]["overall"] - results["V4_st_rate_lead"]["overall"]
sum_marg = sum(d for _, d in marginals[1:])
print(f"\nTotal V0→V4 drop: {total:+.5f}")
print(f"Sum of marginals: {sum_marg:+.5f}  (within 15%? {abs(total - sum_marg) <= 0.15 * abs(total)})")

with open(os.path.join(OUT, "variants.json"), "w") as f:
    json.dump({
        "results": results,
        "tau_star_s": float(tau_star),
        "C_f_hat_Nrad": float(Cf_hat),
        "C_r_hat_Nrad": float(Cr_hat),
        "K_us_prior_s2_m2": float(K_us_prior),
        "marginals_overall": {k: d for k, d in marginals},
    }, f, indent=2)
print("\nsaved", os.path.join(OUT, "variants.json"))
