"""Final fit: per-platform 3-parameter linear correction.

Model: yaw_rate_corr = a + b * pred + c * pred * v^2

Where pred = baseline KS yaw_rate prediction (v/L * tan(delta_road))

Output: out/coeffs.json with per-platform (a, b, c).
For TESLA_MODEL_3 (no truth available), borrow Mach-E coefficients.
"""
import pandas as pd, numpy as np, glob, json, os

OUT = os.path.dirname(os.path.abspath(__file__))
DATA = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-04/data/sim/segments'

coeffs = {}
diag = {}

for plat in ['FORD_F_150_LIGHTNING_MK1','FORD_MUSTANG_MACH_E_MK1','HYUNDAI_IONIQ_5']:
    files = sorted(glob.glob(f'{DATA}/{plat}/*/*/*/sim.csv'))
    n = len(files)
    split = int(n*0.7)
    dtr = pd.concat([pd.read_csv(f) for f in files[:split]])
    dte = pd.concat([pd.read_csv(f) for f in files[split:]])

    truth_tr = dtr['yaw_rate_meas_rads'].values
    pred_tr = dtr['yaw_rate_pred_rads'].values
    v_tr = dtr['v_mps'].values
    m = v_tr > 2.0
    truth_tr, pred_tr, v_tr = truth_tr[m], pred_tr[m], v_tr[m]

    A = np.vstack([np.ones_like(pred_tr), pred_tr, pred_tr*v_tr**2]).T
    coef, *_ = np.linalg.lstsq(A, truth_tr, rcond=None)
    a, b, c = coef.tolist()

    # Eval on test
    truth_te = dte['yaw_rate_meas_rads'].values
    pred_te = dte['yaw_rate_pred_rads'].values
    v_te = dte['v_mps'].values
    pred_te_corr = a + b*pred_te + c*pred_te*v_te**2
    rmse_base = float(np.sqrt(((truth_te - pred_te)**2).mean()))
    rmse_corr = float(np.sqrt(((truth_te - pred_te_corr)**2).mean()))

    # Also full-set retrain for shipping
    all_files = files
    dall = pd.concat([pd.read_csv(f) for f in all_files])
    t_all = dall['yaw_rate_meas_rads'].values
    p_all = dall['yaw_rate_pred_rads'].values
    v_all = dall['v_mps'].values
    m = v_all > 2.0
    t_all, p_all, v_all = t_all[m], p_all[m], v_all[m]
    A_all = np.vstack([np.ones_like(p_all), p_all, p_all*v_all**2]).T
    coef_all, *_ = np.linalg.lstsq(A_all, t_all, rcond=None)
    a, b, c = coef_all.tolist()

    coeffs[plat] = {'a': a, 'b': b, 'c': c}
    diag[plat] = {
        'n_segments': n, 'split_train_test': [split, n-split],
        'rmse_baseline_test': rmse_base,
        'rmse_corrected_test': rmse_corr,
        'improvement_pct_test': 100*(1-rmse_corr/rmse_base),
        'a': a, 'b': b, 'c': c,
    }
    print(f"{plat}: a={a:.4e}  b={b:.4f}  c={c:.4e}  | RMSE base={rmse_base:.5f} -> corr={rmse_corr:.5f}  ({100*(1-rmse_corr/rmse_base):.1f}%)")

# Tesla: borrow from Mach-E (closest in mass/sedan-class). Document this clearly.
coeffs['TESLA_MODEL_3'] = coeffs['FORD_MUSTANG_MACH_E_MK1'].copy()
diag['TESLA_MODEL_3'] = {'note': 'No truth available in Tesla sim segments; borrowed Mach-E coeffs as prior.'}
print(f"\nTESLA_MODEL_3: borrowed Mach-E coefficients (no truth available)")

with open(os.path.join(OUT, 'coeffs.json'),'w') as f:
    json.dump({'coeffs': coeffs, 'diagnostics': diag,
               'model': 'yaw_rate_corr = a + b*yaw_rate_pred_rads + c*yaw_rate_pred_rads*v_mps^2'},
              f, indent=2)
print(f"\nWrote {OUT}/coeffs.json")
