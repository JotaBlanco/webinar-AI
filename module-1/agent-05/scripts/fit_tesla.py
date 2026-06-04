"""For Tesla we have NO yaw_rate_meas_rads in the sim CSVs.
Workaround: derive a proxy truth from wheel speed differential (FL,FR,RL,RR).

yaw_rate_wheels = (v_left - v_right) / track_width
"""
import os, glob, json
import numpy as np
import pandas as pd
from scipy.optimize import minimize

BASE = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-05/data/sim/segments/TESLA_MODEL_3'
TRACK = 1.580  # m, Tesla Model 3 average front+rear track
L = 2.875

paths = []
for root, _, files in os.walk(BASE):
    for f in files:
        if f == 'sim.csv':
            paths.append(os.path.join(root, f))
print(f"Tesla files: {len(paths)}")

deltas, vs, yaws = [], [], []
for p in paths:
    df = pd.read_csv(p, usecols=['delta_road_rad','v_mps','wheel_FL_kph','wheel_FR_kph','wheel_RL_kph','wheel_RR_kph'])
    v_left = ((df.wheel_FL_kph + df.wheel_RL_kph)/2)/3.6
    v_right = ((df.wheel_FR_kph + df.wheel_RR_kph)/2)/3.6
    y_wheel = (v_left - v_right) / TRACK
    deltas.append(df['delta_road_rad'].values)
    vs.append(df['v_mps'].values)
    yaws.append(y_wheel.values)

delta = np.concatenate(deltas)
v = np.concatenate(vs)
y_meas = np.concatenate(yaws)

# Skip stationary samples (wheels too noisy at near-zero v)
mask = v > 3.0
delta, v, y_meas = delta[mask], v[mask], y_meas[mask]
print(f"After v>3 mask: {len(delta)} samples")

# Note: wheel-derived sign convention. Compare to baseline:
y0 = (v / L) * np.tan(delta)
rmse0 = np.sqrt(np.mean((y0 - y_meas)**2))
# Check sign
corr = np.corrcoef(y0, y_meas)[0,1]
print(f"corr baseline vs wheel-yaw: {corr:.4f}")
if corr < 0:
    print("  flipping sign of wheel-derived")
    y_meas = -y_meas
    corr = -corr

rmse0 = np.sqrt(np.mean(((v/L)*np.tan(delta) - y_meas)**2))
print(f"V0 RMSE (wheel-truth proxy) = {rmse0:.5f}")

def loss_v2(p):
    b, Ku = p
    y = (v / L) * np.tan(delta - b) / (1 + Ku * v * v)
    return np.mean((y - y_meas)**2)
r2 = minimize(loss_v2, [0.0, 0.001], method='Nelder-Mead',
              options={'xatol':1e-7,'fatol':1e-9,'maxiter':5000})
b2, Ku2 = r2.x
y2 = (v / L) * np.tan(delta - b2) / (1 + Ku2 * v * v)
rmse2 = np.sqrt(np.mean((y2 - y_meas)**2))
print(f"V2 bias={b2:.5f}, Ku={Ku2:.6f} => RMSE = {rmse2:.5f}")

def loss_v2b(p):
    b, Ku, k = p
    y = (v / L) * np.tan(k * (delta - b)) / (1 + Ku * v * v)
    return np.mean((y - y_meas)**2)
r2b = minimize(loss_v2b, [b2, Ku2, 1.0], method='Nelder-Mead',
               options={'xatol':1e-7,'fatol':1e-9,'maxiter':10000})
b2b, Ku2b, k2b = r2b.x
y2b = (v / L) * np.tan(k2b * (delta - b2b)) / (1 + Ku2b * v * v)
rmse2b = np.sqrt(np.mean((y2b - y_meas)**2))
print(f"V2b bias={b2b:.5f}, Ku={Ku2b:.6f}, k={k2b:.5f} => RMSE = {rmse2b:.5f}")

with open('/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-05/out/tesla_fit.json','w') as f:
    json.dump({
        'note': 'truth proxy = wheel-derived yaw rate (FL+RL minus FR+RR)/2/track',
        'V0_rmse': float(rmse0),
        'V2': {'b': float(b2), 'Ku': float(Ku2), 'rmse': float(rmse2)},
        'V2b': {'b': float(b2b), 'Ku': float(Ku2b), 'k': float(k2b), 'rmse': float(rmse2b)},
    }, f, indent=2)
