"""Fit understeer-gradient correction K_us per platform.

Truth model: yaw_rate_truth = yaw_rate_KS / (1 + K_us * v^2)
=> Linear LS: K_us = sum((pred-truth)*truth*v^2) / sum((truth*v^2)^2)
"""
import pandas as pd, numpy as np, glob, json, os

OUT = os.path.dirname(os.path.abspath(__file__))
DATA = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-04/data/sim/segments'

results = {}
diagnostics = {}

for plat in ['FORD_F_150_LIGHTNING_MK1','FORD_MUSTANG_MACH_E_MK1','HYUNDAI_IONIQ_5']:
    files = sorted(glob.glob(f'{DATA}/{plat}/*/*/*/sim.csv'))
    n = len(files)
    split = int(n*0.7)
    train_files = files[:split]
    test_files = files[split:]
    dtr = pd.concat([pd.read_csv(f) for f in train_files])
    dte = pd.concat([pd.read_csv(f) for f in test_files])
    truth_tr = dtr['yaw_rate_meas_rads'].values
    pred_tr = dtr['yaw_rate_pred_rads'].values
    v_tr = dtr['v_mps'].values
    m = v_tr > 2.0
    truth_tr, pred_tr, v_tr = truth_tr[m], pred_tr[m], v_tr[m]
    num = ((pred_tr - truth_tr) * truth_tr * v_tr**2).sum()
    den = ((truth_tr * v_tr**2)**2).sum()
    K = float(num/den)
    truth_te = dte['yaw_rate_meas_rads'].values
    pred_te = dte['yaw_rate_pred_rads'].values
    v_te = dte['v_mps'].values
    pred_te_corr = pred_te / (1 + K * v_te**2)
    rmse_base = float(np.sqrt(((truth_te - pred_te)**2).mean()))
    rmse_corr = float(np.sqrt(((truth_te - pred_te_corr)**2).mean()))
    results[plat] = K
    diagnostics[plat] = {
        'n_segments': n, 'n_train': split, 'n_test': n-split,
        'K_us': K, 'rmse_baseline': rmse_base, 'rmse_corrected': rmse_corr,
        'improvement_pct': 100*(1-rmse_corr/rmse_base),
    }
    print(f"{plat}: K={K:.6e}  base={rmse_base:.5f}  corr={rmse_corr:.5f}  ({100*(1-rmse_corr/rmse_base):.1f}% better)")

# For Tesla we have no truth — use mean K of other platforms (or pick the closest match by mass: Mach-E mid-weight EV like a sedan)
# Mach-E is the most sedan-like; Tesla shares the production lineage. Use Mach-E K as prior.
results['TESLA_MODEL_3'] = results['FORD_MUSTANG_MACH_E_MK1']
print(f"\nTESLA_MODEL_3: K={results['TESLA_MODEL_3']:.6e}  (borrowed from Mach-E; no truth available)")

with open(os.path.join(OUT, 'kus_fit.json'),'w') as f:
    json.dump({'K_us': results, 'diagnostics': diagnostics}, f, indent=2)
print(f"\nWrote {OUT}/kus_fit.json")
