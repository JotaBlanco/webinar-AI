# Your task (módulo 3 — + planning + verification)

> El reto canónico está en [`../_shared/CHALLENGE.md`](../_shared/CHALLENGE.md) en angle-C, pero como tu aislamiento te prohíbe leer fuera de tu módulo, lo tienes copiado abajo. Esta es la única fuente del reto que debes usar.

---

## Wrapper — componentes del harness disponibles en este módulo

- **Tools (1):** sí.
- **Context-seed (3):** sí, en `CLAUDE.md`.
- **Memory/State (2):** sí, en `AGENTS.md`.
- **Planning (4):** **sí** — `rpi/RPI_INSTRUCTIONS.md` + `rpi/templates/{research,plan}.md`. **Sigue la disciplina:** escribe `research.md` end-to-end *antes* de mirar código, después `plan.md` end-to-end *antes* de escribir python. Guarda artefactos en `rpi/runs/<timestamp>/`.
- **Verification (5):** **sí** — `evals/schema_check.py` (sensor computacional sobre tus CSVs), `evals/baseline_rmse.py` (números baseline reproducibles que tu REPORT.md debe respetar), `evals/consistency_judge.md` (spec del juez inferencial). Regla: computational sensors antes; inferencial solo si lo gana.
- **Modularity (6):** **no** — sin `skills/`.

Si tu CSV no pasa `evals/schema_check.py`, esa variante NO puede entrar en la tabla de ablation.

---

## El reto

[Contenido idéntico al CHALLENGE.md compartido, copiado aquí porque el aislamiento te impide leerlo desde `../_shared/`.]


> Mismo enunciado para los 4 módulos del angle-C. Cada módulo presenta este reto en su `tasks/challenge.md` con un wrapper específico del módulo. Lo que cambia entre módulos NO es el reto: son los componentes del harness disponibles para resolverlo.

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

1. **Baseline.** Asegúrate de que existen sim CSVs Ford recientes (si no, regenéralos a tu carpeta `out/`). Mide y reporta el residual lateral actual (RMSE de ψ̇ en °/s, RMSE de a_y en m/s², coeficiente de correlación predicho-vs-medido, y los regímenes donde el residual es peor — por ejemplo en función de v, |δ|, o |a_y|).
2. **Propón al menos 3 mejoras concretas al modelo lateral.** Ejemplos válidos (no exhaustivos): pasar a Single-Track con tyre cornering stiffness, corrección de bias en yaw-rate, recalibración de wheelbase contra los datos, modelo de neumático no-lineal en alta-G, filtro/lag en δ medido (steering compliance), un término residual aprendido de los datos. Para cada propuesta: hipótesis física, qué señal del residual la sugiere, y cómo medir su contribución.
3. **Implementa 1-2 de esas mejoras** en código (puedes crear nuevos archivos dentro de tu módulo; **no modifiques `code/` en sitio** — copia/extiende a `out/` o a un módulo propio si necesitas). Mantén el modo `clamp_v_to_measured=True` y `clamp_delta_to_measured=True` salvo que justifiques lo contrario.
4. **Re-mide.** Genera sim CSVs con cada variante en tu `out/`. Cuantifica el delta atribuible a cada cambio (ablation: baseline → +cambio_1 → +cambio_1+cambio_2 → ...).
5. **Entrega `REPORT.md`** en la raíz de tu módulo con:
   - Tabla de baseline residual por plataforma (Mach-E, F-150).
   - Lista de mejoras propuestas con su justificación física.
   - Lista de mejoras implementadas con código asociado.
   - Tabla ablation con RMSE antes/después y delta absoluto + relativo.
   - Ranking de impacto: qué cambio merece la pena, cuál no.
   - Limitaciones que te has encontrado.

## Reglas

- **Aislamiento de paths.** Tu mundo de trabajo es esta carpeta de módulo + `code/` (symlink) + `data/` (symlink). **No leas absolutamente nada fuera de estos paths.** En particular: NO accedas a `KB001/`, `KB002/`, `KB003/`, a `webinar-angle-A/`, `webinar-angle-B/`, `webinar-angle-C/_shared/` *ya está incluido en tu wrapper*, ni a `webinar-angle-C/modulo-X/` donde X ≠ tu número de módulo. Si necesitas información que no está accesible en tu módulo, repórtalo como limitación en `REPORT.md`.
- **No escribas en `data/`.** Es shared con otros módulos en ejecución paralela. Todos los CSVs y artefactos van a `modulo-N/out/`.
- **No edites `code/` en sitio.** Es shared. Si necesitas modificar el modelo, copia los ficheros relevantes a `out/` o a un subdirectorio de tu módulo.
- **Reproducibilidad.** Cualquier mejora debe ser ejecutable por otra persona corriendo un comando que dejes documentado.
- **Honestidad.** Si una mejora no mejora, repórtalo igual. La ablation incluye los fracasos.
- **Time budget.** Aproximadamente 20-30 minutos. Si se te va de las manos, entrega lo que tengas con un `REPORT.md` parcial honesto.

## Cómo entregar

Cuando termines, devuelve un resumen ejecutivo (máx 300 palabras) con:
- Baseline RMSE ψ̇ (°/s) por plataforma.
- Mejor RMSE alcanzado y qué cambio(s) lo produjeron.
- Lo más sorprendente que descubriste.
- Bloqueos o información que te hizo falta.
- **Componentes del harness que sentiste que faltaban** (esto es load-bearing para angle-C: el contraste entre módulos es exactamente el contraste entre qué componentes tenías disponibles).
