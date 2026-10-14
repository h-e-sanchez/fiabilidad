"""Catálogo extensible de reglas.

Una regla es una función `(contexto, parametros) -> list[brecha]` registrada con @regla("id").
config/reglas.json decide cuáles corren y con qué parámetros. Para sumar una regla nueva basta con
escribir la función (en src/brechas.py o en otro módulo que se importe) y agregar su entrada al
JSON: el motor no cambia.

Cada brecha es un dict con las columnas de COLUMNAS_BRECHA, para que todas las reglas salgan en
una sola tabla.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

COLUMNAS_BRECHA = ("regla", "subtipo", "componente_id", "referencia", "fecha", "ot_relacionada", "ejecutor", "detalle")
RENUEVAN = {"recambio", "correctiva"}  # tipos de OT que dejan una pieza nueva

REGISTRO: dict[str, Callable[[Contexto, dict], list[dict]]] = {}


def regla(id_regla: str):
    def registrar(funcion):
        if id_regla in REGISTRO:
            raise ValueError(f"La regla «{id_regla}» ya está registrada.")
        REGISTRO[id_regla] = funcion
        return funcion
    return registrar


def brecha(regla: str, componente_id: str, referencia: str, fecha: date, detalle: str, subtipo: str = "",
           ot_relacionada: str = "", ejecutor: str = "") -> dict:
    return {"regla": regla, "subtipo": subtipo, "componente_id": componente_id, "referencia": referencia,
            "fecha": fecha.isoformat(), "ot_relacionada": ot_relacionada, "ejecutor": ejecutor, "detalle": detalle}


@dataclass
class Contexto:
    """Todo lo que una regla puede mirar, ya validado y cruzado."""
    corte: date
    catalogo: dict[str, dict]
    plan: list[dict]
    ots: list[dict]
    fallas: list[dict]  # eventos relevantes, atribuibles a mantenimiento y con componente
    ots_por_componente: dict[str, list[dict]] = field(default_factory=dict)
    fallas_por_componente: dict[str, list[dict]] = field(default_factory=dict)

    def __post_init__(self):
        for ot in sorted(self.ots, key=lambda o: o["fecha_ejecucion"]):
            self.ots_por_componente.setdefault(ot["componente_id"], []).append(ot)
        for f in sorted(self.fallas, key=lambda f: f["fecha_hora"]):
            self.fallas_por_componente.setdefault(f["componente_id"], []).append(f)

    def vida_nominal(self, componente_id: str) -> int:
        return self.catalogo[componente_id]["vida_util_nominal_dias"]

    def ultima_renovacion(self, componente_id: str, antes_de: date) -> date:
        """Fecha en que entró la pieza vigente a esa fecha: último recambio o correctiva, o la instalación."""
        renovacion = self.catalogo[componente_id]["fecha_instalacion"]
        for ot in self.ots_por_componente.get(componente_id, []):
            if ot["fecha_ejecucion"] >= antes_de:
                break
            if ot["tipo_tarea"] in RENUEVAN:
                renovacion = ot["fecha_ejecucion"]
        return renovacion


def ejecutar(contexto: Contexto, config_reglas: list[dict]) -> list[dict]:
    brechas: list[dict] = []
    for entrada in config_reglas:
        if not entrada.get("activa", True):
            continue
        funcion = REGISTRO.get(entrada["id"])
        if funcion is None:
            raise ValueError(f"config/reglas.json pide la regla «{entrada['id']}», que no está registrada.")
        brechas.extend(funcion(contexto, entrada.get("parametros", {})))
    return brechas
