"""Taxonomía cerrada y clasificador por palabras clave.

Cada evento relevante recibe exactamente una categoría de la taxonomía (config/taxonomia.json) o
queda como «no_clasificado» y pasa a la cola de revisión. El clasificador nunca inventa una
categoría: si las palabras clave no alcanzan la confianza mínima, no clasifica.

Confianza = coincidencias de la mejor categoría / coincidencias totales. Un texto que solo nombra
palabras de una categoría tiene confianza 1; uno que mezcla dos categorías por igual, 0,5.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

NO_CLASIFICADO = "no_clasificado"


def normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", sin_tildes.lower()).strip()


@dataclass(frozen=True)
class Categoria:
    id: str
    nombre: str
    atribuible: bool
    palabras: tuple[str, ...]


class Taxonomia:
    def __init__(self, config: dict):
        self.categorias = {
            c["id"]: Categoria(c["id"], c["nombre"], bool(c["atribuible_mantenimiento"]),
                               tuple(normalizar(p) for p in c["palabras_clave"]))
            for c in config["categorias"]
        }
        if NO_CLASIFICADO in self.categorias:
            raise ValueError(f"«{NO_CLASIFICADO}» está reservado: no puede ser una categoría.")

    def atribuible(self, categoria: str) -> bool:
        c = self.categorias.get(categoria)
        return bool(c and c.atribuible)

    def nombre(self, categoria: str) -> str:
        c = self.categorias.get(categoria)
        return c.nombre if c else "No clasificado"


class ClasificadorReglas:
    """Implementación por defecto de la interfaz Clasificador (ver src/llm/interfaz.py)."""

    nombre = "reglas"

    def __init__(self, taxonomia: Taxonomia, confianza_minima: float = 0.6):
        self.taxonomia = taxonomia
        self.confianza_minima = confianza_minima

    def clasificar(self, texto: str) -> tuple[str, float]:
        t = f" {normalizar(texto)} "
        aciertos = {cid: sum(1 for p in c.palabras if f" {p} " in t) for cid, c in self.taxonomia.categorias.items()}
        total = sum(aciertos.values())
        if not total:
            return NO_CLASIFICADO, 0.0
        mejor = max(aciertos, key=lambda cid: aciertos[cid])
        confianza = aciertos[mejor] / total
        if confianza < self.confianza_minima:
            return NO_CLASIFICADO, round(confianza, 3)
        return mejor, round(confianza, 3)
