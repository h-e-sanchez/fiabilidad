# fiabilidad

> *Cruza los eventos de detención de una planta con su plan y su ejecución de mantenimiento, detecta dónde la mantención no está funcionando y propone un plan ajustado con cada cambio justificado. Corre en la terminal o en el navegador, sin que los archivos salgan del equipo.*

**Demo:** <https://h-e-sanchez.github.io/fiabilidad/>

Parte del portafolio **Control de gestión, construido como software**, de Hernán Elías Sánchez:
[`centinela`](https://h-e-sanchez.github.io/centinela/) es la vitrina de reportes Power BI,
[`consulta`](https://h-e-sanchez.github.io/consulta/) es el taller de SQL en el navegador,
[`cartilla`](https://h-e-sanchez.github.io/cartilla/) es el manual de Python y `fiabilidad` es el
modelo de mantenimiento.

## Características de ingeniería

- **Cuatro brechas, un catálogo extensible:** mantención no ejecutada o atrasada, falla posterior a una mantención, recambio redundante por calendario y falla antes de la vida útil nominal. Cada regla es una función registrada con `@regla("id")` y se activa y parametriza en `config/reglas.json`; sumar una no toca el motor.
- **Taxonomía cerrada, nunca inventada:** los eventos se clasifican por palabras clave con un puntaje de confianza; lo que no alcanza la confianza mínima va a una cola de revisión. Un LLM local (Ollama) es un módulo opcional que solo ve esa cola y no puede salir de la taxonomía ([`docs/llm.md`](docs/llm.md)).
- **Plan ajustado en el mismo formato de entrada:** mismas columnas y mismo orden, cada cambio con su regla y su evidencia en `cambios_plan.csv`. La vida útil de referencia mezcla la nominal con la observada por credibilidad ([`docs/modelo.md`](docs/modelo.md)).
- **Medido contra la verdad, cero dependencias:** el generador siembra las brechas y guarda la respuesta en `data/verdad.csv`; los tests exigen encontrar las 226 brechas sembradas, ni una de menos ni una de más. El motor usa solo la biblioteca estándar y el mismo código corre en `pytest`, en la CLI y en la página con [Pyodide](https://pyodide.org/).

## Guía de uso rápido

```bash
pip install -r requirements-dev.txt
python data/generar_datos_sinteticos.py   # Planta Ejemplo SpA: 200 componentes, 100.000 eventos, verdad.csv
python -m src.main                         # analiza data/ y deja los resultados en salida/
python -m src.main --entrada mis_datos --corte 2026-09-30 --salida informe
python -m src.main --llm llama3.1          # segunda opinión con un LLM local (requiere Ollama)
python -m pytest -q
ruff check .
python -m http.server 8000                 # la página en http://localhost:8000
```

Entradas: `catalogo_componentes.csv`, `plan_mantenimiento.csv`, `mantenciones_ejecutadas.csv` y
`eventos_denegacion.csv`, con las columnas de [`docs/especificacion-entradas.md`](docs/especificacion-entradas.md).

Salidas en `salida/`:

| Archivo | Contenido |
|---|---|
| `plan_mantenimiento_ajustado.csv` | El plan con los cambios propuestos, en el formato de entrada |
| `cambios_plan.csv` | Cada cambio: tarea, valor anterior y nuevo, regla y justificación |
| `brechas.csv` | Una fila por brecha detectada, con su referencia (tarea@fecha, OT o evento) |
| `observaciones.csv` | Resumen y prioridad por componente |
| `vida_util.csv` | Vida nominal, observada y ajustada por tipo de componente |
| `clasificacion.csv` / `cola_revision.csv` | Categoría de cada evento relevante y los que quedaron a revisión |
| `informe.md` | Informe legible con todo lo anterior |

El plan de crecimiento está en [`ROADMAP.md`](ROADMAP.md). El despliegue es estático (GitHub
Pages desde `main`), sin paso de build.

## English

A maintenance reliability model by Hernán Elías Sánchez. It cross-checks a plant's service-denial
events against its maintenance plan and executed work orders, flags four gaps (missed or late
maintenance, failures right after maintenance, calendar-driven redundant replacements and failures
before nominal life) and proposes an adjusted plan in the same format as the input, with every
change justified. Event descriptions are classified into a closed taxonomy by keyword rules, with
an optional local LLM (Ollama) for what the rules leave unclassified. The dependency-free engine
runs in the tests, the CLI and the browser through Pyodide, so files never leave the user's device.
Sample data is synthetic and the tests require finding exactly the seeded gaps.

---

Diseñamos el modelo para que cada nueva fuente o regla se sume al catálogo sin reescribir el motor: la confiabilidad del plan mejora con cada antecedente que entra.
