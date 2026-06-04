"""Explore the sim.csv schema and find the truth yaw rate."""
import pandas as pd
import numpy as np

p = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-05/data/sim/segments/TESLA_MODEL_3/063c5f30b8e68fae/00000000--cf682901f4/1/sim.csv'
df = pd.read_csv(p)
print('cols:', df.columns.tolist())
print('shape', df.shape)

# Tesla Model 3 track ~1.580 m. Wheel-derived yaw rate.
track = 1.580
v_left = ((df.wheel_FL_kph + df.wheel_RL_kph)/2)/3.6
v_right = ((df.wheel_FR_kph + df.wheel_RR_kph)/2)/3.6
yaw_wheels = (v_left - v_right) / track  # convention: left-right
print('yaw_wheels mean/std', yaw_wheels.mean(), yaw_wheels.std())
print('psi_dot_rads mean/std', df.psi_dot_rads.mean(), df.psi_dot_rads.std())
print('correlation:', np.corrcoef(yaw_wheels, df.psi_dot_rads)[0,1])
print('delta_road_rad mean:', df.delta_road_rad.mean())
# v_state vs v_mps?
print('v_state vs v_mps diff:', (df.v_state_mps - df.v_mps).abs().max())
