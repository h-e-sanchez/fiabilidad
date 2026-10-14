# ROADMAP

Estado al **2026-10-13**. Este archivo se edita a mano.

## Camino A — Motor · hecho

- [x] Generador de Planta Ejemplo SpA con semilla fija: 200 componentes, plan, OT y 100.000 eventos, con las cuatro brechas sembradas y su verdad
- [x] Especificación de entradas en código (`src/esquemas.py`) y en docs, con un test que las mantiene iguales
- [x] Taxonomía cerrada y clasificador por palabras clave con confianza y cola de revisión
- [x] Catálogo extensible de reglas (`@regla` + `config/reglas.json`) con las cuatro reglas del modelo
- [x] Vida útil por tipo con credibilidad y plan ajustado en el formato de entrada, con cada cambio justificado
- [x] CLI con siete CSV y un informe en Markdown
- [x] Tests contra `verdad.csv`: 100% de las brechas, sin falsos positivos

## Camino B — Página · hecho

- [x] Análisis en el navegador con Pyodide y el mismo `src/`
- [x] Carga de los cuatro CSV propios sin que salgan del equipo (verificado: solo GET al CDN de Pyodide y al contador de visitas)
- [x] Brechas filtrables, componentes prioritarios, cambios al plan, vida útil, cola de revisión y descargas
- [ ] CI con `ruff` + `pytest` en GitHub Actions: el workflow existe en local, pero publicarlo exige `gh auth refresh -s workflow`

## Camino C — LLM local · MVP

- [x] Interfaz `Clasificador` y clasificador híbrido con caché por texto
- [x] Cliente de Ollama sin dependencias, respuesta JSON validada contra la taxonomía
- [x] Tests con servidor falso (validación, caché, errores, textos con instrucciones)
- [ ] Medir precisión sobre las paráfrasis de `verdad_clasificacion.csv` con un modelo real
- [ ] `Redactor` con LLM para las justificaciones, verificando que conserve las cifras
- [ ] Sugerir palabras clave nuevas a partir de lo que resolvió el LLM

## Camino D — Datos reales · pendiente

- [ ] Mapeo de columnas por archivo (para extracciones SAP PM u otras sin renombrar a mano)
- [ ] Fuentes adicionales: horómetros o contadores de uso (vida en horas, no solo en días)
- [ ] Datos censurados en la vida útil (piezas que siguen en servicio), por ejemplo con Kaplan-Meier
- [ ] Tablero Power BI sobre las salidas, al estilo de `centinela`

## Backlog P1 — robustez

- [ ] Aviso visible si Pyodide no carga (sin conexión o CDN bloqueado), con el comando para correr local
- [ ] Probar en el navegador el mismo resultado que en `pytest` (hoy se verificó a mano en Chrome)
