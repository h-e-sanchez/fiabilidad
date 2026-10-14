"""Lectura validada de las entradas y extensibilidad del catálogo de reglas."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pytest

from src import esquemas, reglas
from src.reglas import Contexto, brecha, regla

RAIZ = Path(__file__).resolve().parent.parent


def test_acepta_punto_y_coma_fechas_chilenas_y_decimal_con_coma():
    t = esquemas.leer("eventos_denegacion", "﻿evento_id;fecha_hora;descripcion;duracion_min\n"
                                            "E1;05-03-2026 14:30;Motor quemado;45,5\n")
    fila = t.filas[0]
    assert fila["fecha_hora"] == datetime(2026, 3, 5, 14, 30)  # noqa: DTZ001
    assert fila["duracion_min"] == 45.5
    assert fila["componente_id"] == ""  # opcional y ausente


def test_falta_columna_obligatoria():
    with pytest.raises(esquemas.ErrorEntrada, match="vida_util_nominal_dias"):
        esquemas.leer("catalogo_componentes", "componente_id,tipo_componente,fecha_instalacion\nC1,correa,2025-01-01\n")


def test_reune_todos_los_errores_de_fila():
    texto = ("tarea_id,componente_id,tipo_tarea,frecuencia_dias,fecha_inicio\n"
             "T1,C1,inspeccion,treinta,2025-01-01\n"
             "T1,C1,inspeccion,30,2025-13-01\n"
             "T3,,inspeccion,30,2025-01-01\n")
    with pytest.raises(esquemas.ErrorEntrada) as e:
        esquemas.leer("plan_mantenimiento", texto)
    mensajes = "\n".join(e.value.mensajes)
    assert "fila 2: frecuencia_dias" in mensajes
    assert "fila 3: fecha_inicio" in mensajes
    assert "repetido" in mensajes
    assert "fila 4: componente_id viene vacío" in mensajes


def test_la_especificacion_documentada_coincide_con_el_codigo():
    doc = (RAIZ / "docs/especificacion-entradas.md").read_text(encoding="utf-8")
    for archivo, columnas in esquemas.ESQUEMAS.items():
        assert f"`{archivo}.csv`" in doc, archivo
        seccion = doc.split(f"`{archivo}.csv`", 1)[1].split("\n## ", 1)[0]
        for col, (tipo, obligatoria, _) in columnas.items():
            fila = re.search(rf"^\| `{col}` \| (\w+) \| (sí|no) \|", seccion, re.MULTILINE)
            assert fila, f"{archivo}.{col} no está documentada"
            assert fila.group(1) == tipo and (fila.group(2) == "sí") == obligatoria, f"{archivo}.{col}"


def _contexto() -> Contexto:
    catalogo = {"C1": {"componente_id": "C1", "tipo_componente": "correa", "vida_util_nominal_dias": 100,
                       "fecha_instalacion": date(2026, 1, 1), "equipo_id": "E1"}}
    return Contexto(date(2026, 6, 30), catalogo, [], [], [])


def test_una_regla_nueva_entra_sin_tocar_el_motor():
    @regla("prueba_componente_viejo")
    def viejo(ctx, p):
        return [brecha("prueba_componente_viejo", c, c, ctx.corte, "viejo") for c, f in ctx.catalogo.items()
                if (ctx.corte - f["fecha_instalacion"]).days > p["dias"]]

    try:
        salida = reglas.ejecutar(_contexto(), [{"id": "prueba_componente_viejo", "parametros": {"dias": 90}}])
        assert [b["referencia"] for b in salida] == ["C1"]
        assert reglas.ejecutar(_contexto(), [{"id": "prueba_componente_viejo", "activa": False}]) == []
    finally:
        reglas.REGISTRO.pop("prueba_componente_viejo")


def test_regla_desconocida_en_la_configuracion():
    with pytest.raises(ValueError, match="no está registrada"):
        reglas.ejecutar(_contexto(), [{"id": "no_existe"}])


def test_no_se_puede_registrar_dos_veces():
    from src import brechas  # noqa: F401
    with pytest.raises(ValueError):
        regla("falla_post_mantencion")(lambda ctx, p: [])
