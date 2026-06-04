"""Fit per-platform understeer model:
    yaw_pred = v * (delta - bias) * scale / (L + K_us * v^2)
Compare RMSE vs V0 KS baseline.
"""
import json
import glob
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

BASE = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-02/data'

PLATFORM_L_INIT = {
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
    'FORD_F_150_LIGHTNING_MK1': 3.70,
    'HYUNDAI_IONIQ_5': 2.9,
    'TESLA_MODEL_3': 2.875,
}


def load_truth_data(platform, max_files=None, v_min=3.0):
    files = sorted(glob.glob(f'{BASE}/sim/segments/{platform}/**/sim.csv', recursive=True))
    if max_files:
        files = files[:max_files]
    deltas, vs, yaws = [], [], []
    for f in files:
        df = pd.read_csv(f)
        if 'yaw_rate_meas_rads' not in df.columns:
            continue
        mask = (df['v_mps'].values > v_min) & np.isfinite(df['yaw_rate_meas_rads'].values)
        deltas.append(df.loc[mask, 'delta_road_rad'].values)
        vs.append(df.loc[mask, 'v_mps'].values)
        yaws.append(df.loc[mask, 'yaw_rate_meas_rads'].values)
    if not deltas:
        return None, None, None, files
    return np.concatenate(deltas), np.concatenate(vs), np.concatenate(yaws), files


def model_v1(params, delta, v):
    """Linear bicycle (understeer) model with steering bias.

        yaw = v * (delta - bias) / (L + K_us * v^2)

    L is identifiable when K_us > 0 and v varies. Scale ambiguity removed.
    """
    L, K_us, bias = params
    return v * (delta - bias) / (L + K_us * v ** 2)


def fit_platform(platform, max_files=120):
    delta, v, yaw, files = load_truth_data(platform, max_files=max_files)
    if delta is None:
        return None
    L_init = PLATFORM_L_INIT[platform]
    p0 = [L_init, 0.001, 0.0]
    # bound L to plausible range, K_us non-negative for physical understeer
    bounds = ([1.5, -0.05, -0.05], [5.5, 0.5, 0.05])
    res = least_squares(lambda p: model_v1(p, delta, v) - yaw, p0,
                        bounds=bounds)
    L_fit, K_fit, bias_fit = res.x

    pred_v0 = (v / L_init) * np.tan(delta)
    pred_v1 = model_v1(res.x, delta, v)
    rmse_v0 = float(np.sqrt(np.mean((pred_v0 - yaw) ** 2)))
    rmse_v1 = float(np.sqrt(np.mean((pred_v1 - yaw) ** 2)))
    return {
        'platform': platform,
        'L': float(L_fit), 'K_us': float(K_fit),
        'bias_rad': float(bias_fit),
        'rmse_v0_pooled': rmse_v0, 'rmse_v1_pooled': rmse_v1,
        'n_samples': int(len(delta)),
        'n_files_used': len(files),
    }


if __name__ == '__main__':
    coeffs = {}
    for plat in ['FORD_MUSTANG_MACH_E_MK1', 'FORD_F_150_LIGHTNING_MK1',
                 'HYUNDAI_IONIQ_5']:
        r = fit_platform(plat, max_files=120)
        if r is None:
            print(f'{plat}: NO TRUTH DATA, skipping')
            continue
        print(f"{plat}: L={r['L']:.3f} K_us={r['K_us']:.5f} "
              f"bias={r['bias_rad']:.5f}")
        print(f"  V0 RMSE={r['rmse_v0_pooled']:.5f}  "
              f"V1 RMSE={r['rmse_v1_pooled']:.5f}  "
              f"({(1 - r['rmse_v1_pooled']/r['rmse_v0_pooled']) * 100:.1f}% better)")
        coeffs[plat] = {
            'L': r['L'], 'K_us': r['K_us'],
            'bias_rad': r['bias_rad'],
        }
    # Tesla: no truth — fall back to KS with default L
    coeffs['TESLA_MODEL_3'] = {
        'L': 2.875, 'K_us': 0.0, 'bias_rad': 0.0,
    }
    with open('/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-02/final-model/coeffs.json', 'w') as f:
        json.dump(coeffs, f, indent=2)
    print('Saved coeffs to final-model/coeffs.json')
