"""Vida útil observada por tipo de componente, con ajuste por credibilidad.

Con pocas fallas, el promedio observado es ruidoso: dos fallas tempranas no prueban que la vida
útil real sea la mitad de la nominal. La credibilidad (Bühlmann) pondera ambos datos:

    Z = n / (n + k)        vida_ajustada = Z · vida_media_observada + (1 − Z) · vida_nominal

Con n = 0 manda la nominal; a medida que se acumulan fallas, manda lo observado. k (en
config/reglas.json, «k_credibilidad») es cuántas fallas hacen falta para darles el mismo peso
que a la nominal.

Limitación declarada: solo cuenta las piezas que fallaron, no las que siguen en servicio
(datos censurados), así que la media observada tiende a quedar bajo la real. Por eso el plan
la usa para acortar inspecciones, no para decidir sola un recambio.
"""

from __future__ import annotations

from .reglas import Contexto


def edad_al_fallar(ctx: Contexto, falla: dict) -> int:
    dia = falla["fecha_hora"].date()
    return (dia - ctx.ultima_renovacion(falla["componente_id"], dia)).days


def por_tipo(ctx: Contexto, k: float = 5) -> dict[str, dict]:
    edades: dict[str, list[int]] = {}
    nominal: dict[str, int] = {}
    for comp in ctx.catalogo.values():
        nominal.setdefault(comp["tipo_componente"], comp["vida_util_nominal_dias"])
        edades.setdefault(comp["tipo_componente"], [])
    for f in ctx.fallas:
        edades[ctx.catalogo[f["componente_id"]]["tipo_componente"]].append(edad_al_fallar(ctx, f))
    salida = {}
    for tipo, lista in sorted(edades.items()):
        n = len(lista)
        media = sum(lista) / n if n else None
        z = n / (n + k) if n else 0.0
        ajustada = z * media + (1 - z) * nominal[tipo] if n else float(nominal[tipo])
        salida[tipo] = {"tipo_componente": tipo, "vida_nominal_dias": nominal[tipo], "fallas": n,
                        "vida_media_observada_dias": round(media, 1) if media is not None else "",
                        "credibilidad_z": round(z, 3), "vida_ajustada_dias": round(ajustada, 1)}
    return salida
