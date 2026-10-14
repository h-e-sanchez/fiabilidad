"""La página carga el mismo motor que los tests y las cifras que cita siguen siendo ciertas."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.test_motor import resultado

RAIZ = Path(__file__).resolve().parent.parent


def test_la_pagina_carga_todos_los_modulos_que_usa_el_motor():
    app = (RAIZ / "app.js").read_text(encoding="utf-8")
    cargados = set(re.findall(r'"(\w+\.py)"', app.split("var MODULOS", 1)[1].split(";", 1)[0]))
    # Cierre de imports relativos desde motor.py: lo que la página debe copiar a Pyodide.
    necesarios, pendientes = {"__init__.py"}, ["motor"]
    while pendientes:
        modulo = pendientes.pop()
        if f"{modulo}.py" in necesarios:
            continue
        necesarios.add(f"{modulo}.py")
        arbol = ast.parse((RAIZ / f"src/{modulo}.py").read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom) and nodo.level == 1:
                pendientes += [nodo.module] if nodo.module else [a.name for a in nodo.names]
    assert cargados == necesarios


def test_ids_que_usan_los_scripts_existen_en_el_html():
    html = (RAIZ / "index.html").read_text(encoding="utf-8")
    for script in ("app.js", "tour.js"):
        codigo = (RAIZ / script).read_text(encoding="utf-8")
        assert f'src="{script}' in html, script
        for id_ in set(re.findall(r'\$\("([\w-]+)"\)', codigo)):
            assert f'id="{id_}"' in html, f"{script} usa #{id_}, que no está en index.html"


def test_el_recorrido_usa_el_resultado_vigente_del_motor():
    from herramientas.exportar_demo import texto
    assert (RAIZ / "data/demo.json").read_text(encoding="utf-8") == texto(), "regenera con python -m herramientas.exportar_demo"


def test_los_enlaces_del_indice_de_pasos_llevan_a_una_seccion():
    html = (RAIZ / "index.html").read_text(encoding="utf-8")
    for ancla in set(re.findall(r'href="#([\w-]+)"', html)):
        assert f'id="{ancla}"' in html, ancla


def test_cifras_citadas_coinciden_con_el_motor():
    total = resultado()["resumen"]["brechas"]
    for archivo in ("README.md", "index.html"):
        assert f"{total} brechas sembradas" in (RAIZ / archivo).read_text(encoding="utf-8"), archivo


def test_los_archivos_de_ejemplo_que_pide_la_pagina_existen():
    app = (RAIZ / "app.js").read_text(encoding="utf-8")
    nombres = re.findall(r'"(\w+)"', app.split("var ARCHIVOS", 1)[1].split(";", 1)[0])
    assert nombres and all((RAIZ / f"data/{n}.csv").exists() for n in nombres)
