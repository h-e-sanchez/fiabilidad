"""CLI: analiza una carpeta con los cuatro archivos de entrada y deja los resultados en otra.

Uso:
    python -m src.main                                   # data/ → salida/
    python -m src.main --entrada mis_datos --salida informe --corte 2026-09-30
    python -m src.main --llm llama3.1                    # segunda opinión con un LLM local (Ollama)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import esquemas, motor
from .informe import COLUMNAS_OBS
from .plan import COLUMNAS_CAMBIO
from .reglas import COLUMNAS_BRECHA

RAIZ = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cruza eventos de denegación con la gestión de mantenimiento.")
    parser.add_argument("--entrada", type=Path, default=RAIZ / "data", help="carpeta con los 4 CSV de entrada")
    parser.add_argument("--config", type=Path, default=RAIZ / "config", help="carpeta con reglas.json y taxonomia.json")
    parser.add_argument("--salida", type=Path, default=Path("salida"))
    parser.add_argument("--corte", help="fecha de corte AAAA-MM-DD (por defecto, el último dato)")
    parser.add_argument("--llm", metavar="MODELO", help="modelo de Ollama para lo que las reglas no clasifican")
    parser.add_argument("--llm-url", default="http://localhost:11434")
    args = parser.parse_args(argv)

    faltan = [n for n in esquemas.ARCHIVOS if not (args.entrada / f"{n}.csv").exists()]
    if faltan:
        print(f"Faltan en {args.entrada}: " + ", ".join(f"{n}.csv" for n in faltan), file=sys.stderr)
        return 2
    textos = {n: (args.entrada / f"{n}.csv").read_text(encoding="utf-8-sig") for n in esquemas.ARCHIVOS}
    config_reglas = json.loads((args.config / "reglas.json").read_text(encoding="utf-8"))
    config_tax = json.loads((args.config / "taxonomia.json").read_text(encoding="utf-8"))

    clasificador = None
    if args.llm:
        from .llm.interfaz import ClasificadorHibrido
        from .llm.ollama import ClasificadorOllama
        from .taxonomia import ClasificadorReglas, Taxonomia
        tax = Taxonomia(config_tax)
        clasificador = ClasificadorHibrido(
            ClasificadorReglas(tax, config_reglas.get("clasificacion", {}).get("confianza_minima", 0.6)),
            ClasificadorOllama(tax, args.llm, args.llm_url))
    try:
        r = motor.analizar(textos, config_reglas, config_tax, args.corte, clasificador)
    except esquemas.ErrorEntrada as e:
        print("Los archivos de entrada no cumplen la especificación (docs/especificacion-entradas.md):", file=sys.stderr)
        for m in e.mensajes:
            print(f"  - {m}", file=sys.stderr)
        return 1

    s = args.salida
    s.mkdir(parents=True, exist_ok=True)
    escribir = {
        "brechas.csv": motor.a_csv(r["brechas"], COLUMNAS_BRECHA),
        "observaciones.csv": motor.a_csv(r["observaciones"], COLUMNAS_OBS),
        "clasificacion.csv": motor.a_csv(r["clasificacion"]),
        "cola_revision.csv": motor.a_csv(r["cola_revision"]),
        "vida_util.csv": motor.a_csv(r["vida_util"]),
        "plan_mantenimiento_ajustado.csv": motor.a_csv(r["plan_ajustado"]),
        "cambios_plan.csv": motor.a_csv(r["cambios_plan"], COLUMNAS_CAMBIO),
        "informe.md": r["informe_md"],
    }
    for nombre, texto in escribir.items():
        (s / nombre).write_text(texto, encoding="utf-8")

    t = r["resumen"]
    print(f"Corte {t['corte']}: {t['eventos']} eventos, {t['relevantes']} relevantes, {t['no_clasificados']} a revisión, "
          f"{t['fallas']} fallas atribuibles")
    for regla, n in t["brechas_por_regla"].items():
        print(f"  {t['nombres_reglas'].get(regla, regla)}: {n}")
    print(f"{t['componentes_con_brechas']} componentes con brechas · {t['cambios_plan']} cambios propuestos al plan")
    if clasificador is not None:
        print(f"LLM: {clasificador.consultas_llm} textos distintos consultados a {args.llm}")
    for a in t["advertencias"]:
        print(f"Advertencia: {a}")
    print(f"Resultados en {s}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
