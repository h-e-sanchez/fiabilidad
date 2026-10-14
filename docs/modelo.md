# Cómo funciona el modelo

> *Del evento de detención a un cambio justificado en el plan: seis etapas, cada una con su
> archivo en `src/` y sus parámetros en `config/`.*

| Etapa | Qué hace | Dónde | Parámetro |
|---|---|---|---|
| 1. Ingesta y normalización | Valida cada archivo contra su especificación y convierte tipos (fechas en dos formatos, decimales con coma o punto) | `src/esquemas.py` | — |
| 2. Filtrado | Separa los eventos relevantes por duración | `src/motor.py` | `relevancia.duracion_minima_min` |
| 3. Categorización | Asigna una categoría de la taxonomía cerrada o los manda a revisión | `src/taxonomia.py` | `clasificacion.confianza_minima`, `config/taxonomia.json` |
| 4. Cruce | Une fallas, plan y OT por componente; mide la edad de cada pieza desde su última renovación | `src/reglas.py` (`Contexto`) | — |
| 5. Brechas | Corre las reglas activas del catálogo | `src/brechas.py` | `reglas[]` |
| 6. Observaciones y plan | Prioriza componentes y propone el plan ajustado, con cada cambio justificado | `src/informe.py`, `src/plan.py`, `src/vida_util.py` | `plan.*` |

## Las cuatro reglas

| Regla | Se dispara cuando | Referencia |
|---|---|---|
| `mantencion_no_ejecutada_o_atrasada` | Una fecha que el plan programó no tiene OT (`no_ejecutada`) o la OT se ejecutó más de `tolerancia_dias` después (`atrasada`). Solo se juzgan fechas desde el inicio de la extracción de OT hasta el corte menos la tolerancia. | `tarea@fecha` |
| `falla_post_mantencion` | Una falla del componente ocurre hasta `ventana_dias` después de cualquier OT sobre él (preventiva o correctiva). | `evento_id` |
| `recambio_redundante` | Un recambio preventivo cambia la pieza con menos de `umbral_vida_consumida` de su vida nominal y sin fallas desde la anterior. | `ot_id` |
| `falla_antes_vida_util` | La pieza falla antes de `fraccion_vida_nominal` × su vida nominal, contada desde su último recambio o correctiva (o la instalación). | `evento_id` |

Una falla puede disparar dos reglas a la vez (por ejemplo, temprana y además justo después de una
mantención): son dos hallazgos distintos y se reportan los dos.

### Agregar una regla

```python
# src/brechas.py (o cualquier módulo que importe src/motor.py)
@regla("componente_sin_inspeccion")
def sin_inspeccion(ctx, p):
    ...
    return [brecha("componente_sin_inspeccion", comp, comp, ctx.corte, "Sin inspección en el plan.")]
```

```json
{"id": "componente_sin_inspeccion", "activa": true, "parametros": {}}
```

El motor, el informe y las descargas la incluyen sin más cambios.

## Credibilidad

La vida útil de referencia de cada tipo mezcla la nominal con la observada:

```
Z = n / (n + k)          vida_ajustada = Z · media_observada + (1 − Z) · vida_nominal
```

Con `k = 5`, cinco fallas pesan lo mismo que el dato del fabricante. Así un tipo con dos fallas
tempranas no se declara "malo" por un caso aislado, y uno con treinta sí mueve la referencia. La
media observada solo cuenta piezas que fallaron (no las que siguen en servicio), por lo que tiende
a quedar bajo la real; el plan la usa con esa cautela.

## El plan ajustado

- Sale con las **mismas columnas** que el plan de entrada, en el mismo orden; las tareas
  existentes conservan su `tarea_id` y solo cambia `frecuencia_dias`.
- Las tareas nuevas llevan `tarea_id` `NUEVA-001`, `NUEVA-002`, …
- `cambios_plan.csv` explica cada cambio: regla, valor anterior y nuevo, y la evidencia.
- Las brechas de ejecución (OT atrasadas, fallas tras una mantención) no cambian el plan: son
  observaciones para quien ejecuta, por ejemplo el contratista que concentra fallas posteriores.

## Validación con datos sintéticos

`data/generar_datos_sinteticos.py` siembra las cuatro brechas y deja la respuesta correcta en
`data/verdad.csv`. Los tests exigen que el motor encuentre exactamente esas brechas: ni una de
menos (sensibilidad) ni una de más (precisión). Con datos reales, el equivalente es validar una
muestra de cada regla con el equipo de mantenimiento antes de usar el plan ajustado.
