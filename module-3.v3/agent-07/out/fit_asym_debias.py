"""Add additive bias on top of asym gain; fit (g_left, g_right, b_offset)."""
import sys, glob, json, time
from pathlib import Path
import numpy as np, pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))
from v1_baseline import PLATFORM_PARAMS_V1, _per_segment_delta0
from traj_metrics import cte_diagnostics_segment

ALLOWED = ['t_s','delta_wheel_deg','delta_road_rad','v_mps','a_long_mps2','accel_pedal_pct','brake_pressed','yaw_rate_pred_rads']

def prep(df, plat):
    p = PLATFORM_PARAMS_V1[plat]
    cols = [c for c in ALLOWED if c in df.columns]
    sim = df[cols].copy()
    if p["use_per_segment_delta0"]:
        delta0 = _per_segment_delta0(sim, fallback=p["delta0_fallback"])
    else:
        delta0 = p["delta0"]
    delta_raw = sim['delta_road_rad'].to_numpy() - delta0
    v = sim['v_mps'].to_numpy(); t = sim['t_s'].to_numpy()
    dt = np.diff(t, prepend=t[0])
    return dict(t=t, dt=dt, v=v, delta_raw=delta_raw, mask_v=v>2,
                yt=df['yaw_rate_meas_rads'].to_numpy(),
                L_eff=p['L_eff'], K_us=p['K_us'], tau=p['tau'])

def pred(s, gl, gr, bo, eps=0.005):
    dr=s['delta_raw']
    w = 0.5*(1+np.tanh(dr/eps))
    g = gl*w + gr*(1-w)
    delta = dr*g
    v=s['v']
    yr_ss = v*delta/(s['L_eff']+s['K_us']*v*v)
    alpha = s['dt']/(s['tau']+s['dt'])
    n=len(yr_ss); yr=np.empty(n); yr[0]=yr_ss[0]
    for i in range(1,n):
        yr[i] = (1-alpha[i])*yr[i-1] + alpha[i]*yr_ss[i]
    return yr + bo * (v>2).astype(float)

def scores(segs, gl, gr, bo):
    ysq=0;yn=0;csq=0;cn=0
    for s in segs:
        yr = pred(s, gl, gr, bo)
        m=s['mask_v']; r=(yr-s['yt'])[m]
        ysq+=float((r*r).sum()); yn+=int(m.sum())
        d=cte_diagnostics_segment(s['t'],s['v'],s['yt'],yr)
        csq+=d['sum_sq_m2']; cn+=d['n_bins']
    return np.sqrt(ysq/yn), (np.sqrt(csq/cn) if cn else float('nan'))

def load(plat, n=80):
    paths = sorted(glob.glob(str(ROOT/f"data/sim/segments/{plat}/*/*/*/sim.csv")))[:n]
    return [prep(pd.read_csv(p), plat) for p in paths if 'yaw_rate_meas_rads' in pd.read_csv(p).columns]

asym = json.loads((ROOT/"models/v1-asym-gain/coeffs.json").read_text())
out = {}
for plat in ['FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1', 'HYUNDAI_IONIQ_5']:
    segs = load(plat, n=80)
    p = PLATFORM_PARAMS_V1[plat]
    gl0 = asym[plat]['g_left']; gr0 = asym[plat]['g_right']
    y_a, c_a = scores(segs, gl0, gr0, 0.0)
    print(f"\n=== {plat} (n={len(segs)}) ===")
    print(f"asym: yaw={y_a:.5f}, cte={c_a:.3f}")
    # Optimize all 3
    def loss(x):
        gl, gr, bo = x
        y, c = scores(segs, gl, gr, bo)
        return y/y_a + 0.5*c/c_a
    res = minimize(loss, [gl0, gr0, 0.0], method='Nelder-Mead',
                   options={'xatol':1e-5,'fatol':1e-7,'maxiter':150})
    gl, gr, bo = res.x
    y, c = scores(segs, gl, gr, bo)
    print(f"BEST: gl={gl:.4f}, gr={gr:.4f}, bo={bo:+.6f} -> yaw={y:.5f} ({100*(y-y_a)/y_a:+.1f}%), cte={c:.3f} ({100*(c-c_a)/c_a:+.1f}%)")
    out[plat] = {'g_left': float(gl), 'g_right': float(gr), 'b_offset': float(bo),
                 'blend_eps': 0.005, 'L_eff': p['L_eff'], 'K_us': p['K_us'], 'tau': p['tau'],
                 '_yaw_fit': y, '_cte_fit': c}
with open(ROOT/"models/v1-asym-debias/coeffs.json","w") as f:
    json.dump(out, f, indent=2)
print("\nSaved")
