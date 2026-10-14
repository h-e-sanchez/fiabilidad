/* fiabilidad — corre el motor de src/ en el navegador con Pyodide y pinta el resultado.
   - Carga diferida: Python se descarga recién al primer clic, sin paquetes extra (el motor usa
     solo la biblioteca estándar).
   - Los archivos del visitante se leen con FileReader y se pasan como texto al motor: nunca se
     envían a un servidor. Lo único que se descarga de internet es Pyodide. */
(function () {
  "use strict";

  var VERSION = "0.26.4";
  var BASE = "https://cdn.jsdelivr.net/pyodide/v" + VERSION + "/full/";
  var MODULOS = ["__init__.py", "esquemas.py", "taxonomia.py", "reglas.py", "brechas.py", "vida_util.py",
    "plan.py", "informe.py", "motor.py"];
  var ARCHIVOS = ["catalogo_componentes", "plan_mantenimiento", "mantenciones_ejecutadas", "eventos_denegacion"];
  var COLUMNAS_BRECHA = ["regla", "subtipo", "componente_id", "referencia", "fecha", "ot_relacionada", "ejecutor", "detalle"];
  var MAX_FILAS = 300;
  var cargando = null;
  var ultimo = null;
  var propios = {};
  var $ = function (id) { return document.getElementById(id); };

  function cargarScript(src) {
    return new Promise(function (ok, falla) {
      var s = document.createElement("script");
      s.src = src;
      s.onload = ok;
      s.onerror = function () { falla(new Error("No se pudo descargar Python. Revisa tu conexión.")); };
      document.head.appendChild(s);
    });
  }

  function texto(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error("No se pudo leer " + url);
      return r.text();
    });
  }

  function python(avisar) {
    if (!cargando) {
      cargando = (async function () {
        avisar("Descargando Python (solo la primera vez)…");
        await cargarScript(BASE + "pyodide.js");
        var py = await window.loadPyodide({ indexURL: BASE });
        var dir = py.FS.cwd() + "/src";
        py.FS.mkdirTree(dir);
        var fuentes = await Promise.all(MODULOS.map(function (m) { return texto("src/" + m); }));
        MODULOS.forEach(function (m, i) { py.FS.writeFile(dir + "/" + m, fuentes[i]); });
        var config = await Promise.all([texto("config/reglas.json"), texto("config/taxonomia.json")]);
        py.globals.set("reglas_json", config[0]);
        py.globals.set("taxonomia_json", config[1]);
        return py;
      })();
      cargando.catch(function () { cargando = null; });
    }
    return cargando;
  }

  async function analizar(textos) {
    var avisar = function (t) { $("estado").textContent = t; };
    $("btn-ejemplo").disabled = true;
    $("btn-propios").disabled = true;
    $("errores").hidden = true;
    if (window.analitica) window.analitica.unaVez("analisis-ejecutado");
    try {
      var py = await python(avisar);
      avisar("Analizando…");
      py.globals.set("textos_json", JSON.stringify(textos));
      var json = await py.runPythonAsync("from src import motor\nmotor.analizar_json(textos_json, reglas_json, taxonomia_json)");
      var r = JSON.parse(json);
      if (r.errores) {
        $("errores").innerHTML = r.errores.map(function (e) { return "<li>" + esc(e) + "</li>"; }).join("");
        $("errores").hidden = false;
        avisar("Los archivos no cumplen la especificación.");
        return;
      }
      ultimo = r;
      pintar(r);
      avisar("Listo.");
    } catch (e) {
      avisar("No se pudo analizar: " + String(e && e.message ? e.message : e).split("\n").filter(Boolean).pop());
    } finally {
      $("btn-ejemplo").disabled = false;
      $("btn-propios").disabled = Object.keys(propios).length < ARCHIVOS.length;
    }
  }

  var num = function (n) { return Number(n).toLocaleString("es-CL"); };
  function esc(t) {
    return String(t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  function kpi(valor, rotulo, clase) {
    return '<div class="kpi ' + (clase || "") + '"><span class="valor">' + esc(valor) + '</span><span class="rotulo">' + esc(rotulo) + "</span></div>";
  }
  function tabla(id, columnas, filas, celda) {
    $(id).innerHTML = "<thead><tr>" + columnas.map(function (c) { return "<th" + (c[2] ? ' class="num"' : "") + ">" + esc(c[1]) + "</th>"; }).join("") +
      "</tr></thead><tbody>" + filas.map(function (f) {
        return "<tr>" + columnas.map(function (c) {
          var v = celda ? celda(f, c[0]) : f[c[0]];
          return "<td" + (c[2] ? ' class="num"' : "") + ">" + (v === null || v === undefined ? "" : (c[3] ? v : esc(v))) + "</td>";
        }).join("") + "</tr>";
      }).join("") + "</tbody>";
  }

  function pintar(r) {
    var s = r.resumen;
    $("resultados").hidden = false;
    $("corte").textContent = "al " + s.corte.split("-").reverse().join("-");
    $("kpis").innerHTML =
      kpi(num(s.relevantes), "eventos relevantes de " + num(s.eventos)) +
      kpi(num(s.no_clasificados), "a la cola de revisión", s.no_clasificados ? "alerta" : "ok") +
      kpi(num(s.fallas), "fallas atribuibles a mantenimiento") +
      kpi(num(s.brechas), "brechas detectadas", s.brechas ? "alerta" : "ok") +
      kpi(s.componentes_con_brechas + " de " + s.componentes, "componentes con brechas") +
      kpi(num(s.cambios_plan), "cambios propuestos al plan");

    var reglas = Object.keys(s.brechas_por_regla);
    $("filtros").innerHTML = ['<button type="button" class="chip" aria-pressed="true" data-regla="">Todas (' + s.brechas + ")</button>"]
      .concat(reglas.map(function (k) {
        return '<button type="button" class="chip" aria-pressed="false" data-regla="' + esc(k) + '">' + esc(s.nombres_reglas[k] || k) +
          " (" + s.brechas_por_regla[k] + ")</button>";
      })).join("");
    brechas("");

    tabla("tabla-observaciones", [["componente_id", "Componente"], ["tipo_componente", "Tipo"], ["equipo_id", "Equipo"],
      ["prioridad", "Prioridad", true], ["observacion", "Observación"]], r.observaciones.slice(0, 25));
    tabla("tabla-cambios", [["tarea_id", "Tarea"], ["componente_id", "Componente"], ["accion", "Acción"],
      ["valor_anterior", "Antes"], ["valor_nuevo", "Después"], ["justificacion", "Justificación"]], r.cambios_plan);
    var dec = function (v) { return v === "" ? "—" : Number(v).toLocaleString("es-CL", { maximumFractionDigits: 3 }); };
    tabla("tabla-vida", [["tipo_componente", "Tipo"], ["vida_nominal_dias", "Nominal (días)", true], ["fallas", "Fallas", true],
      ["vida_media_observada_dias", "Media observada", true], ["credibilidad_z", "Z", true], ["vida_ajustada_dias", "Referencia ajustada", true]],
      r.vida_util, function (f, c) { return c === "tipo_componente" ? f[c] : dec(f[c]); });

    var textos = {};
    r.cola_revision.forEach(function (c) { textos[c.descripcion] = (textos[c.descripcion] || 0) + 1; });
    var agrupados = Object.keys(textos).map(function (t) { return { descripcion: t, eventos: textos[t] }; })
      .sort(function (a, b) { return b.eventos - a.eventos; });
    $("nota-cola").textContent = num(r.cola_revision.length) + " eventos en " + agrupados.length +
      " textos distintos que las palabras clave no alcanzan a clasificar. Se revisan una vez por texto, a mano o con el LLM local opcional.";
    tabla("tabla-cola", [["descripcion", "Texto del turno"], ["eventos", "Eventos", true]], agrupados);

    var adv = s.advertencias || [];
    $("advertencias").hidden = !adv.length;
    $("advertencias").innerHTML = adv.map(function (a) { return "<li>" + esc(a) + "</li>"; }).join("");
    $("resultados").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function brechas(regla) {
    var filas = ultimo.brechas.filter(function (b) { return !regla || b.regla === regla; });
    var nombres = ultimo.resumen.nombres_reglas;
    tabla("tabla-brechas", [["regla", "Regla"], ["componente_id", "Componente"], ["fecha", "Fecha"], ["referencia", "Referencia"],
      ["detalle", "Detalle"]], filas.slice(0, MAX_FILAS), function (f, c) {
      if (c === "regla") return f.subtipo ? "Mantención " + f.subtipo.replace("_", " ") : nombres[f.regla];
      return f[c];
    });
    $("nota-brechas").textContent = filas.length > MAX_FILAS ? "Se muestran " + MAX_FILAS + " de " + num(filas.length) +
      "; la descarga trae todas." : "";
  }

  function csv(filas, columnas) {
    if (!filas.length) return (columnas || []).join(",") + "\n";
    var cols = columnas || Object.keys(filas[0]);
    var celda = function (v) { v = v === null || v === undefined ? "" : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
    return [cols.join(",")].concat(filas.map(function (f) { return cols.map(function (c) { return celda(f[c]); }).join(","); })).join("\n") + "\n";
  }
  function descargar(nombre, contenido, tipo) {
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([contenido], { type: (tipo || "text/csv") + ";charset=utf-8" }));
    a.download = nombre;
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }
  function leer(archivo) {
    return new Promise(function (ok, falla) {
      var fr = new FileReader();
      fr.onload = function () { ok(fr.result); };
      fr.onerror = function () { falla(new Error("No se pudo leer " + archivo.name)); };
      fr.readAsText(archivo, "utf-8");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    $("btn-ejemplo").addEventListener("click", async function () {
      $("estado").textContent = "Leyendo los datos de ejemplo…";
      try {
        var textos = await Promise.all(ARCHIVOS.map(function (a) { return texto("data/" + a + ".csv"); }));
        var entrada = {};
        ARCHIVOS.forEach(function (a, i) { entrada[a] = textos[i]; });
        analizar(entrada);
      } catch (e) { $("estado").textContent = e.message; }
    });
    $("archivos").addEventListener("change", function () {
      propios = {};
      Array.prototype.forEach.call(this.files, function (f) {
        var a = ARCHIVOS.filter(function (n) { return f.name.toLowerCase().indexOf(n) >= 0; })[0];
        if (a) propios[a] = f;
      });
      $("detectados").innerHTML = ARCHIVOS.map(function (a) {
        return '<li class="' + (propios[a] ? "ok" : "falta") + '">' + (propios[a] ? "✓ " : "✗ ") + a + (propios[a] ? " ← " + esc(propios[a].name) : " (falta)") + "</li>";
      }).join("");
      $("btn-propios").disabled = Object.keys(propios).length < ARCHIVOS.length;
    });
    $("btn-propios").addEventListener("click", async function () {
      try {
        var textos = await Promise.all(ARCHIVOS.map(function (a) { return leer(propios[a]); }));
        var entrada = {};
        ARCHIVOS.forEach(function (a, i) { entrada[a] = textos[i]; });
        analizar(entrada);
      } catch (e) { $("estado").textContent = e.message; }
    });
    $("filtros").addEventListener("click", function (ev) {
      var b = ev.target.closest(".chip");
      if (!b) return;
      Array.prototype.forEach.call(this.children, function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      brechas(b.dataset.regla);
    });
    $("dl-plan").addEventListener("click", function () { descargar("plan_mantenimiento_ajustado.csv", csv(ultimo.plan_ajustado)); });
    $("dl-cambios").addEventListener("click", function () { descargar("cambios_plan.csv", csv(ultimo.cambios_plan)); });
    $("dl-brechas").addEventListener("click", function () { descargar("brechas.csv", csv(ultimo.brechas, COLUMNAS_BRECHA)); });
    $("dl-observaciones").addEventListener("click", function () { descargar("observaciones.csv", csv(ultimo.observaciones)); });
    $("dl-cola").addEventListener("click", function () { descargar("cola_revision.csv", csv(ultimo.cola_revision)); });
    $("dl-informe").addEventListener("click", function () { descargar("informe.md", ultimo.informe_md, "text/markdown"); });
  });
})();
