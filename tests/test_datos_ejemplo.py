"""El generador es reproducible y los CSV versionados son su salida exacta."""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _generador():
    spec = importlib.util.spec_from_file_location("generador", RAIZ / "data/generar_datos_sinteticos.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["generador"] = modulo  # dataclasses lo busca ahí
    spec.loader.exec_module(modulo)
    return modulo


def test_los_csv_versionados_salen_del_generador_con_la_semilla():
    tablas = _generador().generar()
    for nombre, filas in tablas.items():
        with open(RAIZ / f"data/{nombre}.csv", encoding="utf-8") as f:
            guardadas = list(csv.DictReader(f))
        assert len(guardadas) == len(filas), nombre
        assert guardadas == [{k: str(v) for k, v in fila.items()} for fila in filas], nombre


def test_proporciones_del_aviso():
    g = _generador()
    tablas = g.generar()
    assert len(tablas["eventos_denegacion"]) == g.EVENTOS_TOTALES == 100_000
    assert len(tablas["verdad_clasificacion"]) == g.EVENTOS_RELEVANTES == 10_000
