"""Exporta data/demo.json: el resultado del motor sobre Planta Ejemplo SpA, listo para el recorrido.

La página muestra el recorrido al instante, sin esperar a Python; las cifras salen de aquí.
tests/test_pagina.py exige que este archivo sea idéntico a lo que el motor calcula hoy, así que
un cambio en reglas o datos obliga a regenerarlo:

    python -m herramientas.exportar_demo
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from pathlib import Path

from src import esquemas, motor

RAIZ = Path(__file__).resolve().parent.parent
MUESTRA = {  # columnas que se muestran de cada archivo en el paso 1
    "eventos_denegacion": ["fecha_hora", "equipo_id", "componente_id", "duracion_min", "descripcion"],
    "mantenciones_ejecutadas": ["ot_id", "componente_id", "tipo_tarea", "fecha_programada", "fecha_ejecucion", "ejecutor"],
    "plan_mantenimiento": ["tarea_id", "componente_id", "tipo_tarea", "frecuencia_dias", "fecha_inicio"],
    "catalogo_componentes": ["componente_id", "tipo_componente", "vida_util_nominal_dias", "fecha_instalacion"],
}


def construir() -> dict:
    textos = {n: (RAIZ / f"data/{n}.csv").read_text(encoding="utf-8") for n in esquemas.ARCHIVOS}
    reglas = json.loads((RAIZ / "config/reglas.json").read_text(encoding="utf-8"))
    taxonomia = json.loads((RAIZ / "config/taxonomia.json").read_text(encoding="utf-8"))
    r = motor.analizar(textos, reglas, taxonomia)
    s = r["resumen"]

    muestras = {}
    for nombre, columnas in MUESTRA.items():
        filas = list(csv.DictReader(io.StringIO(textos[nombre])))
        if nombre == "eventos_denegacion":  # una microdetención, una falla y una causa operacional
            elegidas = [next(f for f in filas if float(f["duracion_min"]) < 15),
                        next(f for f in filas if f["componente_id"]),
                        next(f for f in filas if "formato" in f["descripcion"])]
        else:
            elegidas = filas[:3]
        muestras[nombre] = {"filas": len(filas), "columnas": columnas,
                            "ejemplo": [{c: f[c] for c in columnas} for f in elegidas]}

    b = r["brechas"]
    ejemplos = {
        "atrasada": next(x for x in b if x["subtipo"] == "atrasada"),
        "no_ejecutada": next(x for x in b if x["subtipo"] == "no_ejecutada"),
        "falla_post_mantencion": next((x for x in b if x["regla"] == "falla_post_mantencion" and x["ejecutor"] == "Contratista Sur"),
                                      next(x for x in b if x["regla"] == "falla_post_mantencion")),
        "recambio_redundante": next(x for x in b if x["regla"] == "recambio_redundante"),
        "falla_antes_vida_util": next(x for x in b if x["regla"] == "falla_antes_vida_util"),
    }
    c = r["cambios_plan"]
    cambios = [x for x in (next((x for x in c if x["regla"] == "recambio_redundante"), None),
                           next((x for x in c if x["accion"] == "modificar" and x["regla"] == "falla_antes_vida_util"), None),
                           next((x for x in c if x["accion"] == "agregar"), None)) if x]
    subtipos = Counter(x["subtipo"] for x in b if x["regla"] == "mantencion_no_ejecutada_o_atrasada")
    return {
        "resumen": {k: s[k] for k in ("corte", "eventos", "duracion_minima_min", "relevantes", "por_categoria", "no_clasificados",
                                      "fallas", "componentes", "tareas_plan", "ots", "brechas", "brechas_por_regla",
                                      "componentes_con_brechas", "cambios_plan", "nombres_categorias")},
        "textos_en_revision": len({x["descripcion"] for x in r["cola_revision"]}),
        "subtipos_ejecucion": dict(subtipos),
        "post_por_ejecutor": dict(Counter(x["ejecutor"] for x in b if x["regla"] == "falla_post_mantencion").most_common()),
        "muestras": muestras,
        "ejemplos": ejemplos,
        "cambios_ejemplo": cambios,
        "cambios_por_tipo": dict(Counter(f"{x['accion']}:{x['regla']}" for x in c)),
        "vida_util": r["vida_util"],
        "prioritarios": r["observaciones"][:5],
    }


def texto() -> str:
    return json.dumps(construir(), ensure_ascii=False, indent=1) + "\n"


if __name__ == "__main__":
    (RAIZ / "data/demo.json").write_text(texto(), encoding="utf-8")
    print("data/demo.json actualizado")
