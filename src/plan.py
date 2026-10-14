"""Plan de mantenimiento ajustado, en el mismo formato que el plan de entrada.

Las filas conservan las columnas del archivo original, en su orden y con sus valores; solo cambia
lo que una regla justifica. Cada cambio queda en cambios_plan con la regla y la evidencia.

Cambios que propone hoy:
- **Recambio redundante:** alarga la frecuencia del recambio a fraccion_recambio × vida ajustada
  del tipo (solo si la alarga).
- **Fallas antes de la vida útil:** si el tipo acumula al menos fallas_tempranas_minimas, en cada
  componente afectado acorta la inspección (× factor_inspeccion) y, si corre hasta la falla, agrega
  un recambio preventivo a fraccion_recambio × vida ajustada.

Las brechas de ejecución (OT atrasadas, fallas tras una mantención) no cambian el plan: el plan
estaba bien, falló su ejecución. Quedan como observaciones.
"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta

from .esquemas import Tabla
from .informe import num
from .reglas import Contexto

COLUMNAS_CAMBIO = ("tarea_id", "componente_id", "accion", "campo", "valor_anterior", "valor_nuevo", "regla", "justificacion")


def ajustar(tabla_plan: Tabla, ctx: Contexto, brechas: list[dict], vida: dict[str, dict], p: dict
            ) -> tuple[list[dict], list[dict]]:
    fraccion = p.get("fraccion_recambio", 0.85)
    minimas = p.get("fallas_tempranas_minimas", 2)
    factor = p.get("factor_inspeccion", 0.5)
    frecuencia_minima = p.get("frecuencia_minima_dias", 15)

    filas = [dict(c) for c in tabla_plan.crudas]
    tipadas = tabla_plan.filas
    cambios: list[dict] = []
    tarea_de_ot = {o["ot_id"]: o["tarea_id"] for o in ctx.ots}

    def tipo_de(comp: str) -> str:
        return ctx.catalogo[comp]["tipo_componente"] if comp in ctx.catalogo else ""

    def cambiar(i: int, nuevo: int, regla: str, justificacion: str) -> None:
        anterior = filas[i]["frecuencia_dias"]
        filas[i]["frecuencia_dias"] = str(nuevo)
        cambios.append({"tarea_id": filas[i]["tarea_id"], "componente_id": filas[i]["componente_id"], "accion": "modificar",
                        "campo": "frecuencia_dias", "valor_anterior": anterior, "valor_nuevo": str(nuevo),
                        "regla": regla, "justificacion": justificacion})

    # 1) Recambios redundantes: alargar la frecuencia.
    redundantes = Counter(tarea_de_ot.get(b["referencia"], "") for b in brechas if b["regla"] == "recambio_redundante")
    for i, t in enumerate(tipadas):
        n = redundantes.get(t["tarea_id"], 0)
        if not n or t["tipo_tarea"] != "recambio":
            continue
        v = vida.get(tipo_de(t["componente_id"]))
        if not v:
            continue
        nuevo = round(fraccion * v["vida_ajustada_dias"])
        if nuevo > t["frecuencia_dias"]:
            cambiar(i, nuevo, "recambio_redundante",
                    f"{n} recambio(s) con menos vida consumida que el umbral y sin fallas entre ellos. Se lleva al "
                    f"{fraccion:.0%} de la vida de referencia del tipo ({num(v['vida_ajustada_dias'])} días; nominal "
                    f"{num(v['vida_nominal_dias'])}, {v['fallas']} fallas observadas, Z = {num(v['credibilidad_z'], 3)}).")

    # 2) Fallas antes de la vida útil: acortar inspección y, si corre hasta la falla, agregar recambio.
    tempranas = [b for b in brechas if b["regla"] == "falla_antes_vida_util"]
    por_tipo = Counter(tipo_de(b["componente_id"]) for b in tempranas)
    por_comp = Counter(b["componente_id"] for b in tempranas)
    tareas_comp: dict[str, list[int]] = {}
    for i, t in enumerate(tipadas):
        tareas_comp.setdefault(t["componente_id"], []).append(i)
    nuevas = 0
    for comp, n in sorted(por_comp.items()):
        tipo = tipo_de(comp)
        if por_tipo[tipo] < minimas:
            continue
        v = vida[tipo]
        base = (f"{n} falla(s) del componente antes de su vida útil nominal; el tipo «{tipo}» acumula "
                f"{por_tipo[tipo]} y su vida de referencia queda en {num(v['vida_ajustada_dias'])} días "
                f"(nominal {num(v['vida_nominal_dias'])}, Z = {num(v['credibilidad_z'], 3)}).")
        indices = tareas_comp.get(comp, [])
        for i in indices:
            t = tipadas[i]
            if t["tipo_tarea"] == "inspeccion":
                nuevo = max(frecuencia_minima, round(t["frecuencia_dias"] * factor))
                if nuevo < t["frecuencia_dias"]:
                    cambiar(i, nuevo, "falla_antes_vida_util", base + " Se acorta la inspección para detectar el deterioro antes.")
        if not any(tipadas[i]["tipo_tarea"] == "recambio" for i in indices):
            nuevas += 1
            frecuencia = round(fraccion * v["vida_ajustada_dias"])
            inicio = max(ctx.ultima_renovacion(comp, ctx.corte + timedelta(days=1)) + timedelta(days=frecuencia),
                         ctx.corte + timedelta(days=1))
            fila = {c: "" for c in tabla_plan.columnas}
            fila.update({"tarea_id": f"NUEVA-{nuevas:03d}", "componente_id": comp, "tipo_tarea": "recambio",
                         "frecuencia_dias": str(frecuencia), "fecha_inicio": inicio.isoformat()})
            if "descripcion" in fila:
                fila["descripcion"] = f"Recambio preventivo propuesto ({tipo})"
            filas.append(fila)
            cambios.append({"tarea_id": fila["tarea_id"], "componente_id": comp, "accion": "agregar", "campo": "tarea",
                            "valor_anterior": "", "valor_nuevo": f"recambio cada {frecuencia} días desde {inicio.isoformat()}",
                            "regla": "falla_antes_vida_util",
                            "justificacion": base + f" Hoy corre hasta la falla: se propone recambio preventivo al "
                                                    f"{fraccion:.0%} de la vida de referencia."})
    return filas, cambios
