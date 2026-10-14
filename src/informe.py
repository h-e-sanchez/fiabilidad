"""Observaciones por componente e informe en Markdown."""

from __future__ import annotations

from collections import Counter

from .reglas import Contexto


def num(x: float, decimales: int = 1) -> str:
    """Número en formato chileno: miles con punto y decimales con coma."""
    texto = f"{x:,.{decimales}f}" if isinstance(x, float) and not float(x).is_integer() else f"{int(x):,}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")

NOMBRES = {
    "mantencion_no_ejecutada_o_atrasada": "Mantención no ejecutada o atrasada",
    "falla_post_mantencion": "Falla posterior a una mantención",
    "recambio_redundante": "Recambio redundante por calendario",
    "falla_antes_vida_util": "Falla antes de la vida útil nominal",
}
# Prioridad: cada falla pesa 3 (le cuesta a la operación), cada OT no ejecutada o atrasada 1, y los
# recambios redundantes 2 por componente (es un solo hallazgo del plan, se repita las veces que se repita).
PESO_FALLA, PESO_OT, PESO_REDUNDANTE = 3, 1, 2
COLUMNAS_OBS = ("componente_id", "equipo_id", "tipo_componente", "prioridad", "no_ejecutadas", "atrasadas",
                "fallas_post_mantencion", "recambios_redundantes", "fallas_antes_vida_util", "cambios_plan", "observacion")


def observaciones(ctx: Contexto, brechas: list[dict], cambios: list[dict], ventana: int) -> list[dict]:
    por_comp: dict[str, list[dict]] = {}
    for b in brechas:
        por_comp.setdefault(b["componente_id"], []).append(b)
    cambios_comp = Counter(c["componente_id"] for c in cambios)
    filas = []
    for comp, lista in por_comp.items():
        cat = ctx.catalogo.get(comp, {})
        c = Counter((b["regla"], b["subtipo"]) for b in lista)
        no_ej = c[("mantencion_no_ejecutada_o_atrasada", "no_ejecutada")]
        atr = c[("mantencion_no_ejecutada_o_atrasada", "atrasada")]
        post = c[("falla_post_mantencion", "")]
        red = c[("recambio_redundante", "")]
        temp = c[("falla_antes_vida_util", "")]
        frases = []
        if temp:
            frases.append(f"{temp} falla(s) antes de la vida útil nominal")
        if post:
            ejecutores = Counter(b["ejecutor"] for b in lista if b["regla"] == "falla_post_mantencion")
            quien, n = ejecutores.most_common(1)[0]
            frases.append(f"{post} falla(s) hasta {ventana} días después de una mantención ({n} tras OT de {quien})")
        if red:
            frases.append(f"{red} recambio(s) con poca vida consumida")
        if no_ej or atr:
            frases.append(f"{no_ej} mantención(es) no ejecutada(s) y {atr} atrasada(s)")
        if cambios_comp[comp]:
            frases.append(f"{cambios_comp[comp]} cambio(s) propuesto(s) en el plan")
        otras = len(lista) - (no_ej + atr + post + red + temp)  # reglas agregadas al catálogo
        texto = "; ".join(frases)
        prioridad = PESO_FALLA * (post + temp) + PESO_OT * (no_ej + atr + otras) + (PESO_REDUNDANTE if red else 0)
        filas.append({"componente_id": comp, "equipo_id": cat.get("equipo_id", ""), "tipo_componente": cat.get("tipo_componente", ""),
                      "prioridad": prioridad, "no_ejecutadas": no_ej, "atrasadas": atr, "fallas_post_mantencion": post,
                      "recambios_redundantes": red, "fallas_antes_vida_util": temp, "cambios_plan": cambios_comp[comp],
                      "observacion": texto[:1].upper() + texto[1:] + "."})
    return sorted(filas, key=lambda f: (-f["prioridad"], f["componente_id"]))


def markdown(resumen: dict, brechas: list[dict], obs: list[dict], vida: dict[str, dict], cambios: list[dict]) -> str:
    r = resumen
    lineas = [
        f"# Informe de fiabilidad al {r['corte']}",
        "",
        f"- Eventos de denegación: {num(r['eventos'])}; relevantes (≥ {num(r['duracion_minima_min'])} min): {num(r['relevantes'])}.",
        f"- Clasificados en la taxonomía: {num(r['relevantes'] - r['no_clasificados'])}; a revisión: {num(r['no_clasificados'])}.",
        f"- Fallas atribuibles a mantenimiento con componente identificado: {r['fallas']}.",
        f"- Componentes con al menos una brecha: {r['componentes_con_brechas']} de {r['componentes']}.",
        f"- Cambios propuestos al plan: {len(cambios)}.",
        "",
        "## Brechas",
        "",
        "| Regla | Casos |",
        "|---|---:|",
    ]
    for regla, n in r["brechas_por_regla"].items():
        lineas.append(f"| {NOMBRES.get(regla, regla)} | {n} |")
    post = Counter(b["ejecutor"] or "sin dato" for b in brechas if b["regla"] == "falla_post_mantencion")
    if post:
        lineas += ["", "## Fallas posteriores a una mantención, por ejecutor de la OT previa", "",
                   "| Ejecutor | Fallas |", "|---|---:|"]
        lineas += [f"| {e} | {n} |" for e, n in post.most_common()]
    lineas += ["", "## Vida útil por tipo de componente", "",
               "| Tipo | Nominal (días) | Fallas | Media observada | Z | Referencia ajustada |", "|---|---:|---:|---:|---:|---:|"]
    for v in vida.values():
        media = v["vida_media_observada_dias"]
        lineas.append(f"| {v['tipo_componente']} | {num(v['vida_nominal_dias'])} | {v['fallas']} | {num(media) if media != '' else '—'} | "
                      f"{num(v['credibilidad_z'], 3)} | {num(v['vida_ajustada_dias'])} |")
    lineas += ["", "## Componentes prioritarios", "", "| Componente | Tipo | Prioridad | Observación |", "|---|---|---:|---|"]
    lineas += [f"| {o['componente_id']} | {o['tipo_componente']} | {o['prioridad']} | {o['observacion']} |" for o in obs[:15]]
    if cambios:
        lineas += ["", "## Cambios propuestos al plan", "", "| Tarea | Componente | Acción | Antes | Después | Regla |",
                   "|---|---|---|---|---|---|"]
        lineas += [f"| {c['tarea_id']} | {c['componente_id']} | {c['accion']} | {c['valor_anterior']} | {c['valor_nuevo']} | "
                   f"{NOMBRES.get(c['regla'], c['regla'])} |" for c in cambios]
    if r["advertencias"]:
        lineas += ["", "## Advertencias de datos", ""] + [f"- {a}" for a in r["advertencias"]]
    return "\n".join(lineas) + "\n"
