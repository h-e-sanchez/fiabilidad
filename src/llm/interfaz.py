"""Interfaces del módulo LLM: el núcleo no depende de ningún modelo.

El motor solo necesita un objeto con `clasificar(texto) -> (categoria, confianza)`. Las reglas por
palabras clave (src/taxonomia.py) son la implementación por defecto; un LLM entra como segunda
opinión, únicamente para lo que las reglas dejan sin clasificar, y nunca puede salir de la
taxonomía cerrada.
"""

from __future__ import annotations

from typing import Protocol

from ..taxonomia import NO_CLASIFICADO


class Clasificador(Protocol):
    nombre: str

    def clasificar(self, texto: str) -> tuple[str, float]: ...


class Redactor(Protocol):
    """Redacta la justificación de un cambio al plan. Pendiente: hoy la escriben las reglas (src/plan.py)."""

    def justificar(self, cambio: dict) -> str: ...


class ClasificadorHibrido:
    """Reglas primero; el LLM solo ve los textos que las reglas no pudieron clasificar.

    Guarda en caché por texto: en una planta los mismos textos se repiten miles de veces, así que el
    LLM se consulta una vez por texto distinto, no por evento. `ultimo` dice quién clasificó el
    último texto, para dejarlo trazado en la salida.
    """

    def __init__(self, base: Clasificador, llm: Clasificador):
        self.base = base
        self.llm = llm
        self.nombre = f"{base.nombre}+{llm.nombre}"
        self.ultimo = base.nombre
        self.consultas_llm = 0
        self._cache: dict[str, tuple[str, float, str]] = {}

    def clasificar(self, texto: str) -> tuple[str, float]:
        if texto not in self._cache:
            categoria, confianza = self.base.clasificar(texto)
            quien = self.base.nombre
            if categoria == NO_CLASIFICADO:
                self.consultas_llm += 1
                cat_llm, conf_llm = self.llm.clasificar(texto)
                if cat_llm != NO_CLASIFICADO:
                    categoria, confianza, quien = cat_llm, conf_llm, self.llm.nombre
            self._cache[texto] = (categoria, confianza, quien)
        categoria, confianza, self.ultimo = self._cache[texto]
        return categoria, confianza
