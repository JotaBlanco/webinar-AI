"""Diagnose where the residual structure is."""
import pandas as pd, numpy as np, glob

DATA = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-04/data/sim/segments'

# Two-parameter fit: truth = (pred + b)/(1 + K v^2) - add bias term
# Or fit: truth = alpha * pred / (1 + K v^2) -- a multiplicative scale + understeer

for plat in ['FORD_F_150_LIGHTNING_MK1','FORD_MUSTANG_MACH_E_MK1','HYUNDAI_IONIQ_5']:
    files = sorted(glob.glob(f'{DATA}/{plat}/*/*/*/sim.csv'))
    split = int(len(files)*0.7)
    dtr = pd.concat([pd.read_csv(f) for f in files[:split]])
    dte = pd.concat([pd.read_csv(f) for f in files[split:]])

    for label, d in [('train', dtr), ('test', dte)]:
        if label != 'test': continue
        truth = d['yaw_rate_meas_rads'].values
        pred = d['yaw_rate_pred_rads'].values
        v = d['v_mps'].values
        m = v > 2.0
        truth, pred, v = truth[m], pred[m], v[m]

        # Try: truth = alpha * pred / (1 + K v^2) where alpha,K fit
        # Equivalent regression: minimize sum (truth*(1+K v^2) - alpha*pred)^2 -- nonlinear in K
        # Try grid search K then linear LS for alpha
        best = None
        for K in np.linspace(-2e-4, 3e-3, 200):
            denom = 1 + K*v**2
            # alpha = sum(truth*pred*denom) / sum(pred^2) -- wait, truth*denom = alpha*pred -> alpha = sum(truth*denom * pred)/sum(pred^2)
            alpha = (truth*denom*pred).sum() / (pred**2).sum()
            pred_corr = alpha*pred/denom
            rmse = np.sqrt(((truth-pred_corr)**2).mean())
            if best is None or rmse < best[0]:
                best = (rmse, K, alpha)
        rmse_base = np.sqrt(((truth-pred)**2).mean())
        print(f"{plat} ({label}): base={rmse_base:.5f}  alpha,K fit -> K={best[1]:.4e} alpha={best[2]:.4f} rmse={best[0]:.5f}")

        # Also try simple linear: truth = a + b*pred (per platform calibration)
        A = np.vstack([np.ones_like(pred), pred, pred*v**2]).T
        coef, *_ = np.linalg.lstsq(A, truth, rcond=None)
        pred3 = A @ coef
        rmse3 = np.sqrt(((truth-pred3)**2).mean())
        print(f"  linear a+b*pred+c*pred*v^2: a={coef[0]:.4e} b={coef[1]:.4f} c={coef[2]:.4e} rmse={rmse3:.5f}")

        # Distinct: per-segment yaw_rate bias? Check first-row residuals across segments
        # Also: delta_state_rad vs delta_road_rad? -- column same in input.
