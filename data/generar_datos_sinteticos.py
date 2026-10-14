"""Genera los datos sintéticos de Planta Ejemplo SpA: un año de operación, 200 componentes.

Son las cuatro fuentes que el modelo recibe, con la forma de una extracción real:

- **catalogo_componentes.csv:** 200 componentes de 8 tipos en 40 equipos, con su vida útil
  nominal y la fecha de instalación del componente en servicio.
- **plan_mantenimiento.csv:** plan de frecuencia fija. Todos los componentes tienen inspección
  periódica; algunos además tienen recambio por calendario y el resto corre hasta la falla.
- **mantenciones_ejecutadas.csv:** órdenes de trabajo (OT) preventivas generadas por el plan y
  correctivas tras cada falla, como sale de un sistema tipo SAP PM.
- **eventos_denegacion.csv:** ~100.000 eventos de denegación de servicio en el año; ~10% duran
  15 minutos o más (los relevantes). Las fallas reales vienen con texto libre del turno.

Sobre esa base sembramos las cuatro brechas del modelo:

1. Mantenciones no ejecutadas o atrasadas (~4% de las OT del plan).
2. Fallas dentro de los 15 días posteriores a una mantención; más frecuentes después de las OT
   de un contratista.
3. Recambios redundantes: componentes cuyo plan cambia la pieza al 30–50% de su vida útil.
4. Fallas antes de la vida útil nominal, concentradas en dos tipos de componente.

**verdad.csv** guarda cada brecha esperada y **verdad_clasificacion.csv** la categoría real de
cada evento relevante. Los tests exigen que el motor encuentre exactamente esas brechas.

Uso: python data/generar_datos_sinteticos.py   (misma semilla, mismos archivos)
"""

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

SEMILLA = 42
INICIO = date(2025, 10, 1)
FIN = date(2026, 9, 30)
TOLERANCIA_DIAS = 7  # mismos parámetros que config/reglas.json
VENTANA_DIAS = 15
UMBRAL_VIDA = 0.6
EVENTOS_TOTALES = 100_000
EVENTOS_RELEVANTES = 10_000
DIR = Path(__file__).resolve().parent

# tipo: (nombre, vida útil nominal en días, inspección cada N días, categoría de su falla,
#        tasa de falla temprana, textos que escribe el turno al fallar)
TIPOS = {
    "rodamiento": ("Rodamiento", 240, 45, "falla_mecanica", 0.45, [
        "Ruido y vibración en rodamiento", "Rodamiento con desgaste, equipo detenido", "Vibración alta en descanso"]),
    "sello_mecanico": ("Sello mecánico", 180, 30, "fuga", 0.45, [
        "Fuga por sello mecánico", "Goteo constante en sello", "Filtración en sello de bomba"]),
    "correa": ("Correa transportadora", 150, 30, "falla_mecanica", 0.05, [
        "Correa cortada", "Desalineamiento de correa transportadora"]),
    "motor_electrico": ("Motor eléctrico", 720, 90, "falla_electrica", 0.05, [
        "Motor quemado", "Disparo por sobrecorriente en motor", "Falla eléctrica en motor"]),
    "valvula": ("Válvula de control", 365, 60, "falla_mecanica", 0.05, [
        "Válvula con atascamiento", "Rotura de vástago en válvula"]),
    "sensor": ("Sensor de proceso", 300, 60, "falla_instrumentacion", 0.05, [
        "Sensor sin lectura, señal perdida", "Transmisor de presión descalibrado", "Lectura errónea de sensor de nivel"]),
    "contactor": ("Contactor", 400, 90, "falla_electrica", 0.05, [
        "Contactor dañado", "Contactor pegado, cortocircuito en tablero"]),
    "filtro": ("Filtro de línea", 90, 30, "sobrecalentamiento", 0.05, [
        "Temperatura alta por filtro saturado", "Sobrecalentamiento de línea por filtro tapado"]),
}
EJECUTORES = ["Mantención interna", "Contratista Norte", "Contratista Sur"]

RUIDO = {  # eventos relevantes que no son falla de un componente: (categoría real, peso, textos)
    "operacional": ("operacional", 0.55, ["Cambio de formato en línea", "Falta de material en alimentación",
                                          "Espera de operador", "Ajuste de proceso por calidad", "Limpieza programada"]),
    "externo": ("externo", 0.25, ["Corte de suministro eléctrico externo", "Caída de red del proveedor externo",
                                  "Detención por condición climática"]),
    "ambiguo": ("no_clasificado", 0.12, ["Equipo detenido sin detalle", "Detención, revisar", "Parada no informada por turno"]),
}
# Sin palabras clave de la taxonomía: las reglas las dejan sin clasificar; un LLM sí puede leerlas.
PARAFRASIS = [
    ("falla_electrica", "Olor a quemado en tablero y el equipo no parte"),
    ("falla_mecanica", "Ruido metálico fuerte al girar el eje"),
    ("fuga", "Pierde aceite por la base de la bomba"),
    ("sobrecalentamiento", "Carcasa muy caliente al tacto, se detiene"),
    ("falla_instrumentacion", "El indicador de nivel marca cualquier cosa"),
]
PESO_PARAFRASIS = 0.08
MICRO = ["Microdetención por atasco de producto", "Microparada de línea", "Detención breve por ajuste",
         "Parada corta por reinicio de turno"]


@dataclass
class Componente:
    id: str
    equipo: str
    tipo: str
    grupo: str  # normal | redundante | hasta_falla
    instalacion: date
    ots: list[OT] = field(default_factory=list)


@dataclass
class OT:
    componente: str
    tipo_tarea: str
    fecha_ejecucion: date
    ejecutor: str
    tarea_id: str = ""
    fecha_programada: date | None = None
    id: str = ""


@dataclass
class Evento:
    fecha_hora: str
    equipo: str
    componente: str
    duracion: int
    descripcion: str
    categoria: str
    origen: str
    id: str = ""


def vida(tipo: str) -> int:
    return TIPOS[tipo][1]


def generar(semilla: int = SEMILLA) -> dict[str, list]:
    rng = random.Random(semilla)
    componentes: list[Componente] = []
    plan: list[dict] = []
    verdad: list[dict] = []
    ocurrencias: list[tuple[dict, date, Componente]] = []

    nombres_tipo = list(TIPOS)
    for i in range(1, 201):
        tipo = nombres_tipo[(i - 1) % len(nombres_tipo)]
        nombre, L, insp, *_ = TIPOS[tipo]
        r = rng.random()
        grupo = "normal" if r < 0.35 else "redundante" if r < 0.50 else "hasta_falla"
        comp = Componente(f"C{i:03d}", f"EQ{(i - 1) // 5 + 1:02d}", tipo, grupo, INICIO)
        tareas = [("inspeccion", insp, f"Inspección de {nombre.lower()}")]
        if grupo == "hasta_falla":
            comp.instalacion = INICIO - timedelta(days=rng.randint(0, int(0.9 * L)))
        else:
            frac = rng.uniform(0.7, 0.95) if grupo == "normal" else rng.uniform(0.3, 0.5)
            tareas.append(("recambio", round(L * frac), f"Recambio de {nombre.lower()}"))
        for tipo_tarea, frecuencia, descripcion in tareas:
            inicio = INICIO + timedelta(days=rng.randint(0, frecuencia - 1))
            if tipo_tarea == "recambio":
                comp.instalacion = inicio - timedelta(days=frecuencia)  # el primer recambio llega a la edad del plan
            tarea = {"tarea_id": f"T{len(plan) + 1:04d}", "componente_id": comp.id, "tipo_tarea": tipo_tarea,
                     "frecuencia_dias": frecuencia, "fecha_inicio": inicio.isoformat(), "descripcion": descripcion}
            plan.append(tarea)
            d = inicio
            while d <= FIN:
                ocurrencias.append((tarea, d, comp))
                d += timedelta(days=frecuencia)
        componentes.append(comp)

    # OT preventivas: se ejecutan con 0-3 días de holgura, salvo las brechas sembradas (regla 1).
    for tarea, d, comp in ocurrencias:
        ejecucion = d + timedelta(days=rng.randint(-1, 3))
        evaluable = d <= FIN - timedelta(days=55)
        recambio = tarea["tipo_tarea"] == "recambio"
        if evaluable and comp.grupo != "redundante" and rng.random() < 0.04:
            L, frecuencia = vida(comp.tipo), tarea["frecuencia_dias"]
            atraso_max = 40 if not recambio else frecuencia - math.ceil(UMBRAL_VIDA * L) - 5
            ref = f"{tarea['tarea_id']}@{d.isoformat()}"
            if rng.random() < 0.5 and atraso_max >= TOLERANCIA_DIAS + 3:
                ejecucion = d + timedelta(days=rng.randint(TOLERANCIA_DIAS + 3, atraso_max))
                verdad.append({"regla": "mantencion_no_ejecutada_o_atrasada", "subtipo": "atrasada",
                               "referencia": ref, "componente_id": comp.id})
            else:
                verdad.append({"regla": "mantencion_no_ejecutada_o_atrasada", "subtipo": "no_ejecutada",
                               "referencia": ref, "componente_id": comp.id})
                continue
        if ejecucion > FIN:
            continue
        comp.ots.append(OT(comp.id, tarea["tipo_tarea"], ejecucion, rng.choice(EJECUTORES), tarea["tarea_id"], d))
    for comp in componentes:
        comp.ots.sort(key=lambda o: o.fecha_ejecucion)

    # Fallas: solo los componentes que corren hasta la falla; la correctiva renueva la pieza.
    fallas: list[tuple[Evento, Componente, int]] = []
    for comp in componentes:
        if comp.grupo != "hasta_falla":
            continue
        nombre, L, _, categoria, tasa_temprana, textos = TIPOS[comp.tipo]
        renovacion = comp.instalacion
        while True:
            temprana = rng.random() < tasa_temprana
            falla = renovacion + timedelta(days=round(L * (rng.uniform(0.3, 0.75) if temprana else rng.uniform(1.0, 1.4))))
            if falla < INICIO:  # una temprana que habría caído antes de la ventana
                temprana = False
                falla = renovacion + timedelta(days=round(L * rng.uniform(1.0, 1.4)))
            post = False
            if not temprana:
                candidatas = [o for o in comp.ots if o.fecha_ejecucion >= renovacion + timedelta(days=L)
                              and abs((o.fecha_ejecucion - falla).days) <= 30]
                if candidatas:
                    ot = candidatas[0]
                    if rng.random() < (0.6 if ot.ejecutor == "Contratista Sur" else 0.1):
                        falla = ot.fecha_ejecucion + timedelta(days=rng.randint(1, 10))
                        post = True
            if not post:  # fuera de toda ventana posterior a una mantención
                movida = True
                while movida:
                    movida = False
                    for o in comp.ots:
                        if o.fecha_ejecucion <= falla <= o.fecha_ejecucion + timedelta(days=VENTANA_DIAS):
                            falla = o.fecha_ejecucion + timedelta(days=VENTANA_DIAS + 1)
                            movida = True
            if falla > FIN:
                break
            minuto = rng.randint(0, 24 * 60 - 1)
            evento = Evento(f"{falla.isoformat()} {minuto // 60:02d}:{minuto % 60:02d}", comp.equipo, comp.id,
                            rng.randint(30, 480), rng.choice(textos), categoria, "palabra_clave")
            fallas.append((evento, comp, (falla - renovacion).days))
            correctiva = falla + timedelta(days=rng.randint(0, 1))
            if correctiva > FIN:
                break
            comp.ots.append(OT(comp.id, "correctiva", correctiva, rng.choice(EJECUTORES)))
            renovacion = correctiva

    # Eventos: fallas + ruido relevante (sin componente) + microdetenciones irrelevantes.
    eventos = [e for e, _, _ in fallas]
    equipos = sorted({c.equipo for c in componentes})
    dias = (FIN - INICIO).days + 1

    def instante() -> str:
        d = INICIO + timedelta(days=rng.randrange(dias))
        m = rng.randint(0, 24 * 60 - 1)
        return f"{d.isoformat()} {m // 60:02d}:{m % 60:02d}"

    tipos_ruido = list(RUIDO) + ["parafrasis"]
    pesos_ruido = [RUIDO[k][1] for k in RUIDO] + [PESO_PARAFRASIS]
    for _ in range(EVENTOS_RELEVANTES - len(fallas)):
        clase = rng.choices(tipos_ruido, pesos_ruido)[0]
        if clase == "parafrasis":
            categoria, texto = rng.choice(PARAFRASIS)
            origen = "parafrasis"
        else:
            categoria, _, textos = RUIDO[clase]
            texto = rng.choice(textos)
            origen = "ambiguo" if clase == "ambiguo" else "palabra_clave"
        eventos.append(Evento(instante(), rng.choice(equipos), "", rng.randint(15, 240), texto, categoria, origen))
    for _ in range(EVENTOS_TOTALES - EVENTOS_RELEVANTES):
        eventos.append(Evento(instante(), rng.choice(equipos), "", rng.randint(1, 14), rng.choice(MICRO), "", ""))
    eventos.sort(key=lambda e: (e.fecha_hora, e.equipo, e.componente, e.descripcion))
    for n, e in enumerate(eventos, 1):
        e.id = f"EV{n:06d}"

    ots = sorted((o for c in componentes for o in c.ots), key=lambda o: (o.fecha_ejecucion, o.componente, o.tipo_tarea))
    for n, o in enumerate(ots, 1):
        o.id = f"OT{n:05d}"

    # Verdad de las reglas 2, 3 y 4, con la definición de cada regla sobre el estado del generador.
    for evento, comp, edad in fallas:
        dia = date.fromisoformat(evento.fecha_hora[:10])
        if any(o.fecha_ejecucion < dia <= o.fecha_ejecucion + timedelta(days=VENTANA_DIAS) for o in comp.ots):
            verdad.append({"regla": "falla_post_mantencion", "subtipo": "", "referencia": evento.id, "componente_id": comp.id})
        if edad < vida(comp.tipo):
            verdad.append({"regla": "falla_antes_vida_util", "subtipo": "", "referencia": evento.id, "componente_id": comp.id})
    for comp in componentes:
        if comp.grupo == "redundante":
            for o in comp.ots:
                if o.tipo_tarea == "recambio":
                    verdad.append({"regla": "recambio_redundante", "subtipo": "", "referencia": o.id, "componente_id": comp.id})

    return {
        "catalogo_componentes": [{
            "componente_id": c.id, "equipo_id": c.equipo, "tipo_componente": c.tipo,
            "descripcion": f"{TIPOS[c.tipo][0]} {c.equipo}", "vida_util_nominal_dias": vida(c.tipo),
            "fecha_instalacion": c.instalacion.isoformat()} for c in componentes],
        "plan_mantenimiento": plan,
        "mantenciones_ejecutadas": [{
            "ot_id": o.id, "tarea_id": o.tarea_id, "componente_id": o.componente, "tipo_tarea": o.tipo_tarea,
            "fecha_programada": o.fecha_programada.isoformat() if o.fecha_programada else "",
            "fecha_ejecucion": o.fecha_ejecucion.isoformat(), "ejecutor": o.ejecutor} for o in ots],
        "eventos_denegacion": [{
            "evento_id": e.id, "fecha_hora": e.fecha_hora, "equipo_id": e.equipo, "componente_id": e.componente,
            "duracion_min": e.duracion, "descripcion": e.descripcion} for e in eventos],
        "verdad": sorted(verdad, key=lambda v: (v["regla"], v["referencia"])),
        "verdad_clasificacion": [{"evento_id": e.id, "categoria": e.categoria, "origen": e.origen}
                                 for e in eventos if e.duracion >= 15],
    }


def escribir(tablas: dict[str, list], carpeta: Path = DIR) -> None:
    for nombre, filas in tablas.items():
        with open(carpeta / f"{nombre}.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(filas)


if __name__ == "__main__":
    tablas = generar()
    escribir(tablas)
    for nombre, filas in tablas.items():
        print(f"{nombre}.csv: {len(filas):,} filas".replace(",", "."))
    conteo: dict[str, int] = {}
    for v in tablas["verdad"]:
        clave = v["regla"] + (f" ({v['subtipo']})" if v["subtipo"] else "")
        conteo[clave] = conteo.get(clave, 0) + 1
    for clave, n in sorted(conteo.items()):
        print(f"  {clave}: {n}")
