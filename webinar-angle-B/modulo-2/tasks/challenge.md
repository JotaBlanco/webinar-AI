# Challenge — Lateral fidelity of the KS model

## Contexto

Tienes acceso a un modelo Kinematic Single-Track (KS) que predice el comportamiento lateral de un coche a partir de inputs reales capturados por openpilot en dos plataformas Ford (Mustang Mach-E MK1 y F-150 Lightning MK1).

**Modo operativo: speed-known lateral-only.** La velocidad longitudinal `v` y el ángulo de dirección `δ` están *clampados* al valor medido en cada paso. Por construcción, el modelo **no** predice longitudinal — sólo lateral: yaw rate (ψ̇), aceleración lateral (a_y), heading (ψ), posición planar (x, y).

Existen canales de **verdad medida** en los CSVs Ford:
- `yaw_rate_meas_rads` (Yaw_Data_FD1.VehYaw_W_Actl)
- `a_lat_meas_mps2` (BrakeSnData_3.VehLatComp_A_Actl)

Y los residuales ya computados:
- `yaw_rate_resid_rads = yaw_rate_meas_rads - yaw_rate_pred_rads`
- `a_y_resid_mps2 = a_lat_meas_mps2 - a_y_pred_mps2`

## Tu objetivo

**Mejora la fidelidad lateral del modelo, cuantificando la contribución de cada cambio.**

1. **Baseline.** Asegúrate de que existen sim CSVs Ford recientes (si no, regenéralos). Mide y reporta el residual lateral actual (RMSE de ψ̇ en °/s, RMSE de a_y en m/s², coeficiente de correlación predicho-vs-medido, y los regímenes donde el residual es peor — por ejemplo en función de v, |δ|, o |a_y|).
2. **Propón al menos 3 mejoras concretas al modelo lateral.** Ejemplos válidos (no exhaustivos): pasar a Single-Track con tyre cornering stiffness, corrección de bias en yaw-rate, recalibración de wheelbase contra los datos, modelo de neumático no-lineal en alta-G, filtro/lag en δ medido (steering compliance), un término residual aprendido de los datos. Para cada propuesta: hipótesis física, qué señal del residual la sugiere, y cómo medir su contribución.
3. **Implementa 1-2 de esas mejoras** en código (puedes modificar `code/` o crear nuevos archivos en tu módulo). Mantén el modo `clamp_v_to_measured=True` y `clamp_delta_to_measured=True` salvo que justifiques lo contrario.
4. **Re-mide.** Genera sim CSVs con cada variante. Cuantifica el delta atribuible a cada cambio (ablation: baseline → +cambio_1 → +cambio_1+cambio_2 → ...).
5. **Entrega `REPORT.md`** en la raíz de tu módulo con:
   - Tabla de baseline residual por plataforma (Mach-E, F-150).
   - Lista de mejoras propuestas con su justificación física.
   - Lista de mejoras implementadas con código asociado.
   - Tabla ablation con RMSE antes/después y delta absoluto + relativo.
   - Ranking de impacto: qué cambio merece la pena, cuál no.
   - Limitaciones que te has encontrado.

## Reglas

- **Aislamiento.** Tu mundo de trabajo es esta carpeta de módulo + `code/` (symlink) + `data/` (symlink). **No leas absolutamente nada fuera de estos paths.** En particular: NO accedas a `KB001/`, `KB002/`, `KB003/`, ni a otras carpetas del repo `webinar-AI`. Si necesitas información que no está en tu módulo, repórtalo como limitación en `REPORT.md`.
- **Reproducibilidad.** Cualquier mejora debe ser ejecutable por otra persona corriendo un comando que dejes documentado.
- **Honestidad.** Si una mejora no mejora, repórtalo igual. La ablation incluye los fracasos.
- **Time budget.** Aproximadamente 20-30 minutos. Si se te va de las manos, entrega lo que tengas con un `REPORT.md` parcial honesto.

## Cómo entregar

Cuando termines, devuelve un resumen ejecutivo (máx 300 palabras) con:
- Baseline RMSE ψ̇ (°/s) por plataforma.
- Mejor RMSE alcanzado y qué cambio(s) lo produjeron.
- Lo más sorprendente que descubriste.
- Bloqueos o información que te hizo falta.
