"""Compute Tesla understeer K from bicycle model parameters; verify on Hyundai/Mach-E/F-150."""
import numpy as np

cars = {
    'TESLA_MODEL_3': dict(L=2.875, m=2035.0, l_f=1.4375, l_r=1.4375, Cf=222_882, Cr=352_332),
    'FORD_MUSTANG_MACH_E_MK1': dict(L=2.984, m=2336.0, l_f=1.3130, l_r=1.671, Cf=286_551, Cr=355_912),
    'FORD_F_150_LIGHTNING_MK1': dict(L=3.70, m=3084.0, l_f=1.628, l_r=2.072, Cf=378_307, Cr=469_878),
}

# Understeer coefficient K_us in bicycle linear model:
# Steady-state: yr = v*delta / (L + K_us*v^2)
# K_us = m/L * (l_r/Cf - l_f/Cr)  (some sources use different sign; check)
# Actually: K_us = (m/L) * (l_r*Cf - l_f*Cr)/(Cf*Cr)
# Let me use: K_us = m/L^2 * (l_r/Cf - l_f/Cr)  -- need to double-check
# Standard form (Rajamani): yr_ss = v*delta/(L*(1 + K_us*v^2/(L*g)))
# So K_factor in our model = K_us / (L*g)
g = 9.81
for name, c in cars.items():
    L, m, lf, lr, Cf, Cr = c['L'], c['m'], c['l_f'], c['l_r'], c['Cf'], c['Cr']
    K_us_std = m/L * (lr/Cf - lf/Cr)  # rad / (m/s)^2 — actually has g in some defs
    # Form yr = v*delta/(L + K*v^2) means K has units s^2/m
    # Standard: yr/delta = v/(L + K_us*v^2)  with K_us = (m/L)*(lf/Cr*L_r? )/...)
    # Let's derive: linear bicycle steady-state yaw rate gain:
    #   yr/delta = v / (L * (1 + (m*v^2/L) * (lr*Cr - lf*Cf)/(Cf*Cr*L)))
    # = v / (L + m*v^2 * (lr*Cr - lf*Cf)/(Cf*Cr*L))
    # Wait, simpler: K [s^2/m] = m * (lr*Cr - lf*Cf) / (Cf*Cr*L^2)
    K = m * (lr*Cr - lf*Cf) / (Cf*Cr*L)
    # Above: yr = v*delta/(L + K*v^2)
    K2 = m/(L) * (lr/Cf - lf/Cr) / 1.0
    K3 = m*(lf*Cf - lr*Cr) / (L * Cf * Cr)
    print(f'{name}: K (signed) v1={K:.5f}  v2={K2:.5f}  v3={K3:.5f}')

# Fit-derived K
fit_K = {'HYUNDAI_IONIQ_5': 0.00339, 'FORD_MUSTANG_MACH_E_MK1': 0.00263, 'FORD_F_150_LIGHTNING_MK1': 0.00354}
for k,v in fit_K.items():
    print(f'  Fit: {k} K={v:.5f}')
