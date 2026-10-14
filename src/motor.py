"""Pipeline completo: ingesta → filtrado → clasificación → cruce → brechas → observaciones y plan.

Recibe los archivos como texto y devuelve todo como dicts y listas, sin tocar el disco ni la red:
la misma función corre en pytest, en la CLI (src/main.py) y en la página con Pyodide, de modo que
los archivos de un cliente nunca tienen que salir de su equipo.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from datetime import date

from . import brechas as _brechas  # noqa: F401  (registra las reglas)
from . import esquemas, informe, plan, reglas, vida_util
from .taxonomia import NO_CLASIFICADO, ClasificadorReglas, Taxonomia

ORDEN_REGLAS = tuple(informe.NOMBRES)


def analizar(textos: dict[str, str], config_reglas: dict, config_taxonomia: dict, corte: str | None = None,
             clasificador=None) -> dict:
    tablas = {nombre: esquemas.leer(nombre, textos[nombre]) for nombre in esquemas.ARCHIVOS}
    advertencias: list[str] = []
    catalogo = {f["componente_id"]: f for f in tablas["catalogo_componentes"].filas}

    plan_filas = []
    for t in tablas["plan_mantenimiento"].filas:
        if t["componente_id"] in catalogo:
            plan_filas.append(t)
        else:
            advertencias.append(f"Tarea {t['tarea_id']}: el componente {t['componente_id']} no está en el catálogo; se omite.")
    ots = []
    for o in tablas["mantenciones_ejecutadas"].filas:
        if o["componente_id"] in catalogo:
            ots.append(o)
        else:
            advertencias.append(f"OT {o['ot_id']}: el componente {o['componente_id']} no está en el catálogo; se omite.")
    eventos = tablas["eventos_denegacion"].filas

    fecha_corte = date.fromisoformat(corte) if corte else max(
        [o["fecha_ejecucion"] for o in ots] + [e["fecha_hora"].date() for e in eventos])

    # Filtrado y clasificación con la taxonomía cerrada.
    taxonomia = Taxonomia(config_taxonomia)
    minima = config_reglas.get("relevancia", {}).get("duracion_minima_min", 15)
    confianza = config_reglas.get("clasificacion", {}).get("confianza_minima", 0.6)
    clasificador = clasificador or ClasificadorReglas(taxonomia, confianza)
    relevantes = [e for e in eventos if e["duracion_min"] >= minima and e["fecha_hora"].date() <= fecha_corte]
    clasificacion, fallas = [], []
    sin_componente = 0
    for e in relevantes:
        categoria, conf = clasificador.clasificar(e["descripcion"])
        clasificacion.append({"evento_id": e["evento_id"], "fecha_hora": e["fecha_hora"].isoformat(sep=" ", timespec="minutes"),
                              "equipo_id": e["equipo_id"], "componente_id": e["componente_id"],
                              "duracion_min": e["duracion_min"], "descripcion": e["descripcion"],
                              "categoria": categoria, "confianza": conf, "clasificado_por": getattr(clasificador, "ultimo", None)
                              or getattr(clasificador, "nombre", "reglas")})
        if taxonomia.atribuible(categoria):
            if e["componente_id"] in catalogo:
                fallas.append({**e, "categoria": categoria})
            else:
                sin_componente += 1
    if sin_componente:
        advertencias.append(f"{sin_componente} fallas atribuibles sin componente identificado en el catálogo: no entran al cruce.")

    ctx = reglas.Contexto(fecha_corte, catalogo, plan_filas, ots, fallas)
    lista = reglas.ejecutar(ctx, config_reglas["reglas"])
    lista.sort(key=lambda b: (ORDEN_REGLAS.index(b["regla"]) if b["regla"] in ORDEN_REGLAS else 99, b["fecha"], b["referencia"]))

    p_plan = config_reglas.get("plan", {})
    vida = vida_util.por_tipo(ctx, p_plan.get("k_credibilidad", 5))
    plan_ajustado, cambios = plan.ajustar(tablas["plan_mantenimiento"], ctx, lista, vida, p_plan)
    ventana = next((r["parametros"].get("ventana_dias", 15) for r in config_reglas["reglas"] if r["id"] == "falla_post_mantencion"), 15)
    obs = informe.observaciones(ctx, lista, cambios, ventana)

    por_regla = Counter(b["regla"] for b in lista)
    resumen = {
        "corte": fecha_corte.isoformat(),
        "eventos": len(eventos),
        "duracion_minima_min": minima,
        "relevantes": len(relevantes),
        "por_categoria": dict(Counter(c["categoria"] for c in clasificacion).most_common()),
        "no_clasificados": sum(1 for c in clasificacion if c["categoria"] == NO_CLASIFICADO),
        "fallas": len(fallas),
        "componentes": len(catalogo),
        "tareas_plan": len(plan_filas),
        "ots": len(ots),
        "brechas": len(lista),
        "brechas_por_regla": {r: por_regla[r] for r in ORDEN_REGLAS if r in por_regla} | {
            r: n for r, n in por_regla.items() if r not in ORDEN_REGLAS},
        "componentes_con_brechas": len(obs),
        "cambios_plan": len(cambios),
        "advertencias": advertencias,
        "nombres_reglas": informe.NOMBRES,
        "nombres_categorias": {c: taxonomia.nombre(c) for c in list(taxonomia.categorias) + [NO_CLASIFICADO]},
    }
    return {
        "resumen": resumen,
        "brechas": lista,
        "observaciones": obs,
        "clasificacion": clasificacion,
        "cola_revision": [c for c in clasificacion if c["categoria"] == NO_CLASIFICADO],
        "vida_util": list(vida.values()),
        "plan_ajustado": plan_ajustado,
        "cambios_plan": cambios,
        "informe_md": informe.markdown(resumen, lista, obs, vida, cambios),
    }


def analizar_json(textos_json: str, reglas_json: str, taxonomia_json: str, corte: str = "") -> str:
    """Puerta de entrada para la página: todo entra y sale como texto JSON."""
    try:
        r = analizar(json.loads(textos_json), json.loads(reglas_json), json.loads(taxonomia_json), corte or None)
    except esquemas.ErrorEntrada as e:
        return json.dumps({"errores": e.mensajes}, ensure_ascii=False)
    r.pop("clasificacion")  # 10.000 filas que la página no muestra; la CLI sí las escribe
    return json.dumps(r, ensure_ascii=False)


def a_csv(filas: list[dict], columnas: list[str] | tuple[str, ...] | None = None) -> str:
    salida = io.StringIO()
    columnas = list(columnas or (filas[0].keys() if filas else []))
    w = csv.DictWriter(salida, fieldnames=columnas, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    w.writerows(filas)
    return salida.getvalue()
