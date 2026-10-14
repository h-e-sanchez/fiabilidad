"""El motor contra la verdad de terreno de los datos de ejemplo."""

from __future__ import annotations

import csv
import functools
import json
from pathlib import Path

from src import esquemas, motor

RAIZ = Path(__file__).resolve().parent.parent


def textos() -> dict[str, str]:
    return {n: (RAIZ / f"data/{n}.csv").read_text(encoding="utf-8") for n in esquemas.ARCHIVOS}


def config() -> tuple[dict, dict]:
    return (json.loads((RAIZ / "config/reglas.json").read_text(encoding="utf-8")),
            json.loads((RAIZ / "config/taxonomia.json").read_text(encoding="utf-8")))


@functools.lru_cache(maxsize=1)
def resultado() -> dict:
    return motor.analizar(textos(), *config())


def leer_csv(nombre: str) -> list[dict]:
    with open(RAIZ / f"data/{nombre}.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_encuentra_exactamente_las_brechas_sembradas():
    esperadas = {(v["regla"], v["subtipo"], v["referencia"]) for v in leer_csv("verdad")}
    encontradas = {(b["regla"], b["subtipo"], b["referencia"]) for b in resultado()["brechas"]}
    assert encontradas - esperadas == set(), "falsos positivos"
    assert esperadas - encontradas == set(), "brechas sin detectar"


def test_cada_regla_tiene_casos_sembrados():
    por_regla = resultado()["resumen"]["brechas_por_regla"]
    assert set(por_regla) == {"mantencion_no_ejecutada_o_atrasada", "falla_post_mantencion",
                              "recambio_redundante", "falla_antes_vida_util"}
    assert all(n > 0 for n in por_regla.values())


def test_clasificacion_por_reglas_contra_la_verdad():
    verdad = {v["evento_id"]: v for v in leer_csv("verdad_clasificacion")}
    clasificados = resultado()["clasificacion"]
    assert len(clasificados) == len(verdad)
    for c in clasificados:
        v = verdad[c["evento_id"]]
        # Las paráfrasis no traen palabras clave: las reglas las dejan a revisión (ahí entra el LLM).
        esperada = "no_clasificado" if v["origen"] == "parafrasis" else v["categoria"]
        assert c["categoria"] == esperada, (c["descripcion"], c["categoria"], esperada)


def test_plan_ajustado_conserva_el_formato_de_entrada():
    original = leer_csv("plan_mantenimiento")
    ajustado = resultado()["plan_ajustado"]
    assert list(ajustado[0]) == list(original[0])
    assert [f["tarea_id"] for f in ajustado[: len(original)]] == [f["tarea_id"] for f in original]
    cambios = {c["tarea_id"]: c for c in resultado()["cambios_plan"]}
    for antes, despues in zip(original, ajustado):
        if antes != despues:
            assert antes["tarea_id"] in cambios, "cambio sin justificar"
            assert {k for k in antes if antes[k] != despues[k]} == {"frecuencia_dias"}
    for nueva in ajustado[len(original):]:
        assert nueva["tarea_id"].startswith("NUEVA-") and nueva["tarea_id"] in cambios


def test_cada_cambio_tiene_regla_y_justificacion():
    cambios = resultado()["cambios_plan"]
    assert cambios
    for c in cambios:
        assert c["regla"] in ("recambio_redundante", "falla_antes_vida_util")
        assert len(c["justificacion"]) > 40


def test_recambios_redundantes_alargan_y_tempranas_acortan():
    original = {f["tarea_id"]: int(f["frecuencia_dias"]) for f in leer_csv("plan_mantenimiento")}
    for c in resultado()["cambios_plan"]:
        if c["accion"] != "modificar":
            continue
        if c["regla"] == "recambio_redundante":
            assert int(c["valor_nuevo"]) > original[c["tarea_id"]]
        else:
            assert int(c["valor_nuevo"]) < original[c["tarea_id"]]


def test_observaciones_ordenadas_por_prioridad():
    obs = resultado()["observaciones"]
    assert [o["prioridad"] for o in obs] == sorted((o["prioridad"] for o in obs), reverse=True)
    assert obs[0]["fallas_antes_vida_util"] + obs[0]["fallas_post_mantencion"] > 0


def test_credibilidad_sin_fallas_usa_la_nominal():
    for v in resultado()["vida_util"]:
        if v["fallas"] == 0:
            assert v["vida_ajustada_dias"] == v["vida_nominal_dias"]
        else:
            assert 0 < v["credibilidad_z"] < 1


def test_corte_explicito_reduce_lo_evaluado():
    temprano = motor.analizar(textos(), *config(), corte="2026-03-31")
    assert temprano["resumen"]["corte"] == "2026-03-31"
    assert temprano["resumen"]["relevantes"] < resultado()["resumen"]["relevantes"]


def test_analizar_json_devuelve_errores_legibles():
    malos = textos() | {"catalogo_componentes": "componente_id,tipo_componente\nC001,rodamiento\n"}
    r = json.loads(motor.analizar_json(json.dumps(malos), *(json.dumps(c) for c in config())))
    assert "errores" in r and "vida_util_nominal_dias" in r["errores"][0]
