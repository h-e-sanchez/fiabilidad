"""Las cuatro reglas de brecha entre el plan, la ejecución y las fallas.

Cada una se registra en src/reglas.py y toma sus parámetros de config/reglas.json.
"""

from __future__ import annotations

from datetime import timedelta

from .reglas import Contexto, brecha, regla


@regla("mantencion_no_ejecutada_o_atrasada")
def no_ejecutada_o_atrasada(ctx: Contexto, p: dict) -> list[dict]:
    """Recorre cada fecha que el plan programó y busca su OT por (tarea, fecha programada).

    Solo se juzgan las fechas desde el inicio de la extracción de OT y hasta el corte menos la
    tolerancia: una tarea programada ayer todavía no está atrasada.
    """
    tolerancia = p.get("tolerancia_dias", 7)
    if not ctx.ots:
        return []
    desde = min(o["fecha_ejecucion"] for o in ctx.ots) - timedelta(days=tolerancia)
    hasta = ctx.corte - timedelta(days=tolerancia)
    por_programa = {(o["tarea_id"], o["fecha_programada"]): o for o in ctx.ots if o["tarea_id"] and o["fecha_programada"]}
    salida = []
    for tarea in ctx.plan:
        if tarea["frecuencia_dias"] <= 0:
            continue
        d = tarea["fecha_inicio"]
        paso = timedelta(days=tarea["frecuencia_dias"])
        while d <= hasta:
            if d >= desde:
                ref = f"{tarea['tarea_id']}@{d.isoformat()}"
                ot = por_programa.get((tarea["tarea_id"], d))
                if ot is None:
                    salida.append(brecha("mantencion_no_ejecutada_o_atrasada", tarea["componente_id"], ref, d,
                                         f"{tarea['tipo_tarea'].capitalize()} programada el {d.isoformat()} sin OT al corte.",
                                         subtipo="no_ejecutada"))
                else:
                    atraso = (ot["fecha_ejecucion"] - d).days
                    if atraso > tolerancia:
                        salida.append(brecha("mantencion_no_ejecutada_o_atrasada", tarea["componente_id"], ref, d,
                                             f"{tarea['tipo_tarea'].capitalize()} ejecutada con {atraso} días de atraso "
                                             f"(tolerancia {tolerancia}).", subtipo="atrasada",
                                             ot_relacionada=ot["ot_id"], ejecutor=ot["ejecutor"]))
            d += paso
    return salida


@regla("falla_post_mantencion")
def falla_post_mantencion(ctx: Contexto, p: dict) -> list[dict]:
    """Una falla del mismo componente hasta N días después de una OT: la intervención no resolvió."""
    ventana = p.get("ventana_dias", 15)
    salida = []
    for f in ctx.fallas:
        dia = f["fecha_hora"].date()
        previas = [o for o in ctx.ots_por_componente.get(f["componente_id"], [])
                   if o["fecha_ejecucion"] < dia <= o["fecha_ejecucion"] + timedelta(days=ventana)]
        if previas:
            ot = previas[-1]
            dias = (dia - ot["fecha_ejecucion"]).days
            salida.append(brecha("falla_post_mantencion", f["componente_id"], f["evento_id"], dia,
                                 f"«{f['descripcion']}» {dias} días después de la OT {ot['ot_id']} ({ot['tipo_tarea']}).",
                                 ot_relacionada=ot["ot_id"], ejecutor=ot["ejecutor"]))
    return salida


@regla("recambio_redundante")
def recambio_redundante(ctx: Contexto, p: dict) -> list[dict]:
    """Recambio preventivo con poca vida consumida y sin fallas desde la pieza anterior."""
    umbral = p.get("umbral_vida_consumida", 0.6)
    salida = []
    for ot in ctx.ots:
        if ot["tipo_tarea"] != "recambio" or ot["componente_id"] not in ctx.catalogo:
            continue
        comp = ot["componente_id"]
        renovacion = ctx.ultima_renovacion(comp, ot["fecha_ejecucion"])
        edad = (ot["fecha_ejecucion"] - renovacion).days
        vida = ctx.vida_nominal(comp)
        consumida = edad / vida
        fallo = any(renovacion < f["fecha_hora"].date() <= ot["fecha_ejecucion"] for f in ctx.fallas_por_componente.get(comp, []))
        if consumida < umbral and not fallo:
            salida.append(brecha("recambio_redundante", comp, ot["ot_id"], ot["fecha_ejecucion"],
                                 f"Pieza cambiada a los {edad} días: {consumida:.0%} de su vida útil nominal ({vida} días), "
                                 f"sin fallas desde la anterior.", ot_relacionada=ot["ot_id"], ejecutor=ot["ejecutor"]))
    return salida


@regla("falla_antes_vida_util")
def falla_antes_vida_util(ctx: Contexto, p: dict) -> list[dict]:
    """La pieza falló antes de cumplir su vida útil nominal (edad desde su última renovación)."""
    fraccion = p.get("fraccion_vida_nominal", 1.0)
    salida = []
    for f in ctx.fallas:
        dia = f["fecha_hora"].date()
        comp = f["componente_id"]
        edad = (dia - ctx.ultima_renovacion(comp, dia)).days
        vida = ctx.vida_nominal(comp)
        if edad < fraccion * vida:
            salida.append(brecha("falla_antes_vida_util", comp, f["evento_id"], dia,
                                 f"«{f['descripcion']}» a los {edad} días de servicio: {edad / vida:.0%} de su vida útil "
                                 f"nominal ({vida} días)."))
    return salida
