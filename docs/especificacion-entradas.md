# Especificación de los archivos de entrada

> *Qué tiene que traer cada archivo para que el modelo lo procese. Si un archivo no cumple, el
> modelo lo rechaza con la lista de problemas antes de analizar nada.*

Reglas comunes a los cuatro archivos:

- CSV con encabezado, en UTF-8 y separado por coma o por punto y coma (se detecta solo).
- Los nombres de columna no distinguen mayúsculas. Las columnas extra se aceptan y se conservan:
  el plan ajustado sale con todas las columnas del plan de entrada, en su mismo orden.
- **Obligatoria** significa que la columna existe y trae valor en todas las filas. Una opcional
  puede faltar entera.
- Tipos: `texto`; `entero`; `decimal` (acepta `45.5` o `45,5`); `fecha` (`AAAA-MM-DD` o
  `DD-MM-AAAA`); `fecha_hora` (fecha seguida de `HH:MM`).
- La llave de cada archivo (la primera columna) no se puede repetir.
- Las OT y las tareas cuyo componente no está en el catálogo se omiten con una advertencia en el
  informe; no detienen el análisis.

Esta tabla es la misma que `src/esquemas.py`; un test verifica que no se desalineen.


## `catalogo_componentes.csv`

Es la base del cruce: todo lo demás se une por `componente_id`.

| Columna | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `componente_id` | texto | sí | Identificador único del componente (la llave del cruce). |
| `equipo_id` | texto | no | Equipo al que pertenece. |
| `tipo_componente` | texto | sí | Tipo de pieza; agrupa la vida útil observada. |
| `descripcion` | texto | no | Nombre legible. |
| `vida_util_nominal_dias` | entero | sí | Vida útil nominal del fabricante o del estándar interno, en días. |
| `fecha_instalacion` | fecha | sí | Fecha en que la pieza actual entró en servicio. |

## `plan_mantenimiento.csv`

Plan de frecuencia fija: cada tarea se programa en `fecha_inicio` y luego cada `frecuencia_dias`. Solo `recambio` renueva la pieza.

| Columna | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `tarea_id` | texto | sí | Identificador único de la tarea del plan. |
| `componente_id` | texto | sí | Componente sobre el que se ejecuta. |
| `tipo_tarea` | texto | sí | inspeccion, recambio u otra; solo recambio renueva la pieza. |
| `frecuencia_dias` | entero | sí | Cada cuántos días se programa (plan de frecuencia fija). |
| `fecha_inicio` | fecha | sí | Primera fecha programada; las siguientes suman la frecuencia. |
| `descripcion` | texto | no | Texto libre de la tarea. |

## `mantenciones_ejecutadas.csv`

Extracción de órdenes de trabajo (en SAP PM, por ejemplo, de las transacciones IW38/IW39). La OT preventiva se une con el plan por `tarea_id` + `fecha_programada`. `recambio` y `correctiva` renuevan la pieza: desde ahí se mide su edad.

| Columna | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `ot_id` | texto | sí | Identificador único de la orden de trabajo. |
| `tarea_id` | texto | no | Tarea del plan que originó la OT; vacío en las correctivas. |
| `componente_id` | texto | sí | Componente intervenido. |
| `tipo_tarea` | texto | sí | inspeccion, recambio, correctiva u otra; recambio y correctiva renuevan la pieza. |
| `fecha_programada` | fecha | no | Fecha del plan que cumple la OT (vacía en las correctivas). |
| `fecha_ejecucion` | fecha | sí | Fecha real de ejecución. |
| `ejecutor` | texto | no | Equipo interno o contratista que ejecutó. |

## `eventos_denegacion.csv`

Solo los eventos con `duracion_min` ≥ 15 (parámetro `relevancia.duracion_minima_min`) se clasifican. Solo los que caen en una categoría atribuible a mantenimiento y traen `componente_id` entran al cruce.

| Columna | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `evento_id` | texto | sí | Identificador único del evento. |
| `fecha_hora` | fecha_hora | sí | Inicio del evento. |
| `equipo_id` | texto | no | Equipo afectado. |
| `componente_id` | texto | no | Componente responsable, si el turno lo identificó. |
| `duracion_min` | decimal | sí | Duración de la denegación en minutos; filtra los relevantes. |
| `descripcion` | texto | sí | Texto libre del turno; es lo que se clasifica. |
