"""Especificación de los archivos de entrada y su lectura validada.

Cada archivo es un CSV con encabezado (coma o punto y coma, UTF-8). Una columna obligatoria debe
existir y venir con valor en todas las filas; una opcional puede faltar entera. Si algo no cumple,
`leer` reúne todos los problemas en un solo ErrorEntrada antes de procesar nada: es mejor rechazar
el archivo con un mensaje claro que analizar datos a medias.

docs/especificacion-entradas.md es la versión para personas de este mismo diccionario; un test
verifica que ambos digan lo mismo.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime

# archivo -> columna -> (tipo, obligatoria, descripción)
ESQUEMAS: dict[str, dict[str, tuple[str, bool, str]]] = {
    "catalogo_componentes": {
        "componente_id": ("texto", True, "Identificador único del componente (la llave del cruce)."),
        "equipo_id": ("texto", False, "Equipo al que pertenece."),
        "tipo_componente": ("texto", True, "Tipo de pieza; agrupa la vida útil observada."),
        "descripcion": ("texto", False, "Nombre legible."),
        "vida_util_nominal_dias": ("entero", True, "Vida útil nominal del fabricante o del estándar interno, en días."),
        "fecha_instalacion": ("fecha", True, "Fecha en que la pieza actual entró en servicio."),
    },
    "plan_mantenimiento": {
        "tarea_id": ("texto", True, "Identificador único de la tarea del plan."),
        "componente_id": ("texto", True, "Componente sobre el que se ejecuta."),
        "tipo_tarea": ("texto", True, "inspeccion, recambio u otra; solo recambio renueva la pieza."),
        "frecuencia_dias": ("entero", True, "Cada cuántos días se programa (plan de frecuencia fija)."),
        "fecha_inicio": ("fecha", True, "Primera fecha programada; las siguientes suman la frecuencia."),
        "descripcion": ("texto", False, "Texto libre de la tarea."),
    },
    "mantenciones_ejecutadas": {
        "ot_id": ("texto", True, "Identificador único de la orden de trabajo."),
        "tarea_id": ("texto", False, "Tarea del plan que originó la OT; vacío en las correctivas."),
        "componente_id": ("texto", True, "Componente intervenido."),
        "tipo_tarea": ("texto", True, "inspeccion, recambio, correctiva u otra; recambio y correctiva renuevan la pieza."),
        "fecha_programada": ("fecha", False, "Fecha del plan que cumple la OT (vacía en las correctivas)."),
        "fecha_ejecucion": ("fecha", True, "Fecha real de ejecución."),
        "ejecutor": ("texto", False, "Equipo interno o contratista que ejecutó."),
    },
    "eventos_denegacion": {
        "evento_id": ("texto", True, "Identificador único del evento."),
        "fecha_hora": ("fecha_hora", True, "Inicio del evento."),
        "equipo_id": ("texto", False, "Equipo afectado."),
        "componente_id": ("texto", False, "Componente responsable, si el turno lo identificó."),
        "duracion_min": ("decimal", True, "Duración de la denegación en minutos; filtra los relevantes."),
        "descripcion": ("texto", True, "Texto libre del turno; es lo que se clasifica."),
    },
}
ARCHIVOS = tuple(ESQUEMAS)
LLAVES = {"catalogo_componentes": "componente_id", "plan_mantenimiento": "tarea_id",
          "mantenciones_ejecutadas": "ot_id", "eventos_denegacion": "evento_id"}
MAX_MENSAJES = 12


class ErrorEntrada(ValueError):
    def __init__(self, mensajes: list[str]):
        self.mensajes = mensajes
        super().__init__("\n".join(mensajes))


@dataclass
class Tabla:
    nombre: str
    columnas: list[str]   # encabezado original, en su orden: el plan ajustado lo respeta
    crudas: list[dict]    # valores tal como vienen (texto)
    filas: list[dict]     # valores convertidos a su tipo


_FECHA = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$|^(\d{2})[-/](\d{2})[-/](\d{4})$")


def a_fecha(texto: str) -> date:
    m = _FECHA.match(texto)
    if not m:
        raise ValueError
    if m.group(1):
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return date(int(m.group(6)), int(m.group(5)), int(m.group(4)))


def a_fecha_hora(texto: str) -> datetime:
    partes = texto.replace("T", " ").split()
    d = a_fecha(partes[0])
    if len(partes) == 1:
        return datetime(d.year, d.month, d.day)  # noqa: DTZ001  hora local de la planta, sin zona
    hms = [int(x) for x in partes[1].split(":")]
    return datetime(d.year, d.month, d.day, *hms)  # noqa: DTZ001


def a_decimal(texto: str) -> float:
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto)


CONVERTIR = {"texto": str, "entero": lambda t: int(a_decimal(t)), "decimal": a_decimal,
             "fecha": a_fecha, "fecha_hora": a_fecha_hora}
FORMATO = {"texto": "texto", "entero": "número entero", "decimal": "número", "fecha": "fecha AAAA-MM-DD o DD-MM-AAAA",
           "fecha_hora": "fecha y hora AAAA-MM-DD HH:MM"}


def leer(nombre: str, texto: str) -> Tabla:
    """Lee y valida un archivo; lanza ErrorEntrada con todos los problemas encontrados."""
    esquema = ESQUEMAS[nombre]
    texto = texto.lstrip("﻿")
    primera = texto.split("\n", 1)[0]
    separador = ";" if primera.count(";") > primera.count(",") else ","
    lector = csv.reader(io.StringIO(texto), delimiter=separador)
    try:
        encabezado = [c.strip().lower() for c in next(lector)]
    except StopIteration:
        raise ErrorEntrada([f"{nombre}: el archivo está vacío."]) from None
    faltan = [c for c, (_, obligatoria, _) in esquema.items() if obligatoria and c not in encabezado]
    if faltan:
        raise ErrorEntrada([f"{nombre}: faltan las columnas obligatorias {', '.join(faltan)}."])

    errores: list[str] = []
    crudas, filas, vistas = [], [], set()
    llave = LLAVES[nombre]
    for n, valores in enumerate(lector, start=2):
        if not any(v.strip() for v in valores):
            continue
        cruda = {c: (valores[i].strip() if i < len(valores) else "") for i, c in enumerate(encabezado)}
        fila = {}
        for col, (tipo, obligatoria, _) in esquema.items():
            valor = cruda.get(col, "")
            if valor == "":
                if obligatoria:
                    errores.append(f"{nombre}, fila {n}: {col} viene vacío.")
                fila[col] = None if tipo != "texto" else ""
                continue
            try:
                fila[col] = CONVERTIR[tipo](valor)
            except (ValueError, TypeError, IndexError):
                errores.append(f"{nombre}, fila {n}: {col} = «{valor}» no es {FORMATO[tipo]}.")
        if fila.get(llave) in vistas:
            errores.append(f"{nombre}, fila {n}: {llave} «{fila[llave]}» está repetido.")
        vistas.add(fila.get(llave))
        crudas.append(cruda)
        filas.append(fila)
        if len(errores) >= MAX_MENSAJES:
            errores.append(f"{nombre}: hay más errores; corrige estos y vuelve a cargar.")
            break
    if errores:
        raise ErrorEntrada(errores)
    if not filas:
        raise ErrorEntrada([f"{nombre}: no trae filas de datos."])
    return Tabla(nombre, encabezado, crudas, filas)
