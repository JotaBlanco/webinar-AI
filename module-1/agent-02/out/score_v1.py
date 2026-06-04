"""Score the V1 predictor.

Loads sim-only (input-only) segments, calls predict(), then loads the
matching sim segment (truth) to compute:
  - yaw-rate RMSE (rad/s)
  - distance-resampled cross-track-error RMSE (m)

The 'distance-resampled XTE' is computed by resampling both predicted
and truth trajectories to a uniform arc-length grid (1 m), then taking
the perpendicular distance between curves at matched arc-length samples.
This is an approximation of the canonical grader's distance-resampled XTE.

Splits files 80/20 train/holdout by hash for honest held-out reporting.
"""
import sys
import glob
import json
import hashlib
import numpy as np
import pandas as pd

sys.path.insert(0, '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-02/final-model')
from predict import predict  # noqa: E402

BASE = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-02/data'


def is_holdout(path: str, holdout_frac: float = 0.2) -> bool:
    h = int(hashlib.md5(path.encode()).hexdigest(), 16)
    return (h % 100) < (holdout_frac * 100)


def truth_path(sim_only_path: str) -> str:
    return sim_only_path.replace('/sim-only/', '/sim/')


def xte_distance_resampled(t_pred, x_pred, y_pred,
                            t_true, x_true, y_true,
                            ds=1.0) -> float:
    """Distance-resampled cross-track-error RMSE.

    Builds arc-length parametrisations s_pred(t) and s_true(t),
    resamples (x,y) on a common s-grid at spacing ds, then takes
    the planar distance between paired samples.
    """
    sp = np.zeros_like(t_pred)
    sp[1:] = np.cumsum(np.hypot(np.diff(x_pred), np.diff(y_pred)))
    st = np.zeros_like(t_true)
    st[1:] = np.cumsum(np.hypot(np.diff(x_true), np.diff(y_true)))

    s_max = float(min(sp[-1], st[-1]))
    if s_max < 5.0:
        return float('nan')
    s_grid = np.arange(0.0, s_max, ds)

    xp = np.interp(s_grid, sp, x_pred)
    yp = np.interp(s_grid, sp, y_pred)
    xt = np.interp(s_grid, st, x_true)
    yt = np.interp(s_grid, st, y_true)

    return float(np.sqrt(np.mean((xp - xt) ** 2 + (yp - yt) ** 2)))


PLATFORMS_WITH_TRUTH = [
    'FORD_MUSTANG_MACH_E_MK1',
    'FORD_F_150_LIGHTNING_MK1',
    'HYUNDAI_IONIQ_5',
]


def score(max_files_per_platform=None):
    rows = []
    for plat in PLATFORMS_WITH_TRUTH:
        sim_only_files = sorted(glob.glob(
            f'{BASE}/sim-only/segments/{plat}/**/sim.csv', recursive=True))
        if max_files_per_platform:
            sim_only_files = sim_only_files[:max_files_per_platform]
        for f in sim_only_files:
            tf = truth_path(f)
            try:
                sim_in = pd.read_csv(f)
                truth = pd.read_csv(tf)
            except Exception:
                continue
            # V0 baseline already in sim-only as yaw_rate_pred_rads
            yaw_truth = truth['yaw_rate_meas_rads'].to_numpy()
            yaw_v0 = sim_in['yaw_rate_pred_rads'].to_numpy()
            # V1 predict
            try:
                out = predict(sim_in.drop(columns=['yaw_rate_pred_rads']),
                              plat)
            except Exception as e:
                print(f'predict failed on {f}: {e}')
                continue
            yaw_v1 = out['yaw_rate_pred_rads'].to_numpy()

            rmse_v0 = float(np.sqrt(np.mean((yaw_v0 - yaw_truth) ** 2)))
            rmse_v1 = float(np.sqrt(np.mean((yaw_v1 - yaw_truth) ** 2)))

            # V0 trajectory by integrating V0 yaw with measured v.
            # TRUTH trajectory by integrating measured yaw (yaw_rate_meas_rads)
            # — the sim.csv x_m/y_m columns are themselves V0-derived, not GPS.
            t_arr = sim_in['t_s'].to_numpy()
            v_arr = sim_in['v_mps'].to_numpy()
            from predict import _integrate_trajectory
            x_v0, y_v0 = _integrate_trajectory(t_arr, v_arr, yaw_v0)
            x_tr, y_tr = _integrate_trajectory(t_arr, v_arr, yaw_truth)

            xte_v0 = xte_distance_resampled(
                t_arr, x_v0, y_v0, t_arr, x_tr, y_tr)
            xte_v1 = xte_distance_resampled(
                t_arr, out['x_m'].to_numpy(), out['y_m'].to_numpy(),
                t_arr, x_tr, y_tr)

            rows.append({
                'platform': plat,
                'file': f,
                'holdout': is_holdout(f),
                'rmse_yaw_v0': rmse_v0,
                'rmse_yaw_v1': rmse_v1,
                'xte_v0_m': xte_v0,
                'xte_v1_m': xte_v1,
            })
    df = pd.DataFrame(rows)
    return df


if __name__ == '__main__':
    df = score()
    df.to_csv('/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-02/out/score_v1_per_segment.csv', index=False)

    print('\n=== ALL segments (per platform) ===')
    for plat, g in df.groupby('platform'):
        print(f'{plat}  n={len(g)}')
        print(f'  yaw RMSE  V0 mean={g.rmse_yaw_v0.mean():.5f}  '
              f'V1 mean={g.rmse_yaw_v1.mean():.5f}  '
              f'({(1 - g.rmse_yaw_v1.mean()/g.rmse_yaw_v0.mean())*100:.1f}%)')
        print(f'  XTE V0 mean={g.xte_v0_m.mean():.3f} m  '
              f'XTE V1 mean={g.xte_v1_m.mean():.3f} m  '
              f'({(1 - g.xte_v1_m.mean()/g.xte_v0_m.mean())*100:.1f}%)')

    hold = df[df['holdout']]
    print(f'\n=== HOLDOUT (20% by md5) n={len(hold)} ===')
    for plat, g in hold.groupby('platform'):
        print(f'{plat}  n={len(g)}')
        print(f'  yaw RMSE  V0 mean={g.rmse_yaw_v0.mean():.5f}  '
              f'V1 mean={g.rmse_yaw_v1.mean():.5f}')
        print(f'  XTE  V0 mean={g.xte_v0_m.mean():.3f} m  '
              f'V1 mean={g.xte_v1_m.mean():.3f} m')

    summary = {
        'overall': {
            'yaw_rmse_v0_mean': float(df.rmse_yaw_v0.mean()),
            'yaw_rmse_v1_mean': float(df.rmse_yaw_v1.mean()),
            'xte_v0_mean_m': float(df.xte_v0_m.mean()),
            'xte_v1_mean_m': float(df.xte_v1_m.mean()),
            'n_segments': int(len(df)),
        },
        'holdout': {
            'yaw_rmse_v0_mean': float(hold.rmse_yaw_v0.mean()),
            'yaw_rmse_v1_mean': float(hold.rmse_yaw_v1.mean()),
            'xte_v0_mean_m': float(hold.xte_v0_m.mean()),
            'xte_v1_mean_m': float(hold.xte_v1_m.mean()),
            'n_segments': int(len(hold)),
        },
        'per_platform': {
            plat: {
                'yaw_rmse_v0_mean': float(g.rmse_yaw_v0.mean()),
                'yaw_rmse_v1_mean': float(g.rmse_yaw_v1.mean()),
                'xte_v0_mean_m': float(g.xte_v0_m.mean()),
                'xte_v1_mean_m': float(g.xte_v1_m.mean()),
                'n': int(len(g)),
            }
            for plat, g in df.groupby('platform')
        }
    }
    with open('/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-02/out/score_summary.json', 'w') as fh:
        json.dump(summary, fh, indent=2)
    print('\nWrote out/score_summary.json')
