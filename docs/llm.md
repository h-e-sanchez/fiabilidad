# Módulo LLM (opcional y local)

> *Un LLM como segunda opinión para los textos que las palabras clave no alcanzan a clasificar,
> sin que los datos de la planta salgan del equipo y sin salir nunca de la taxonomía cerrada.*

## Por qué está fuera del núcleo

- **Ecosistema cerrado:** el núcleo corre sin red. Un LLM en la nube obligaría a enviar los textos
  de la planta a un tercero; uno local (Ollama) no.
- **Trazabilidad:** las reglas por palabras clave son auditables línea por línea. El LLM solo
  entra donde ellas no deciden, y cada evento queda marcado con quién lo clasificó
  (`clasificado_por` en `clasificacion.csv`).
- **Costo:** en una planta los textos se repiten. El clasificador híbrido consulta al LLM una vez
  por texto distinto, no por evento. Con los datos de ejemplo son 8 textos para 1.995 eventos.

## Piezas

| Archivo | Qué es |
|---|---|
| `src/llm/interfaz.py` | `Clasificador` (protocolo), `Redactor` (protocolo, para la siguiente etapa) y `ClasificadorHibrido` (reglas primero, LLM para lo dudoso, con caché por texto) |
| `src/llm/ollama.py` | `ClasificadorOllama`: llama a `http://localhost:11434/api/chat` con `urllib` (sin dependencias), respuesta forzada a JSON y validada contra la taxonomía |
| `tests/test_llm.py` | Pruebas contra un servidor Ollama falso: validación, caché, errores y resistencia a textos que intentan dar instrucciones |

## Uso

```bash
# 1. Instalar Ollama (https://ollama.com) y descargar un modelo
ollama pull llama3.1
# 2. Correr el análisis con segunda opinión
python -m src.main --llm llama3.1
```

La CLI informa cuántos textos distintos consultó. La página web no usa LLM: corre solo con
reglas, para que el demo funcione en cualquier navegador.

## Garantías

- **No inventa categorías:** cualquier respuesta fuera de `config/taxonomia.json` cuenta como
  `no_clasificado`.
- **Los textos son datos:** el prompt lo declara y la validación acota el efecto de un texto
  malicioso a, como mucho, una categoría equivocada.
- **Determinismo:** `temperature = 0`.

## Medición pendiente

`data/verdad_clasificacion.csv` marca con `origen = parafrasis` los eventos escritos sin palabras
clave (por ejemplo, «Pierde aceite por la base de la bomba» → `fuga`). Son la vara para medir el
LLM: qué porcentaje de esas paráfrasis clasifica bien. La medición queda pendiente hasta correrla
con Ollama instalado; no publicamos una cifra que no hayamos medido.

## Siguiente etapa

- `Redactor` con LLM: reescribir la justificación de cada cambio del plan en lenguaje de
  planta, conservando las cifras que calcularon las reglas (se verificaría que cada número del
  texto exista en la evidencia).
- Proponer palabras clave nuevas para la taxonomía a partir de lo que el LLM resolvió, para que
  la próxima corrida lo haga con reglas.
