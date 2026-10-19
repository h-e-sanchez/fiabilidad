/* fiabilidad — recorrido para quien evalúa el proyecto.
   Pinta los pasos 1 a 4 con data/demo.json (el resultado del motor sobre la planta de ejemplo,
   exportado por herramientas/exportar_demo.py), así el recorrido se lee al instante, sin esperar a
   que cargue Python. El análisis en vivo está en app.js. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var num = function (n) { return Number(n).toLocaleString("es-CL", { maximumFractionDigits: 1 }); };
  function esc(t) {
    return String(t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  function fecha(iso) { return iso ? iso.slice(0, 10).split("-").reverse().join("-") : ""; }

  var FUENTES = [
    ["eventos_denegacion", "Eventos de detención", "Cada detención con su duración y lo que anotó el turno."],
    ["mantenciones_ejecutadas", "Órdenes de trabajo ejecutadas", "Lo que de verdad se hizo: preventivas y correctivas."],
    ["plan_mantenimiento", "Plan de mantenimiento", "Qué se programa, sobre qué componente y cada cuántos días."],
    ["catalogo_componentes", "Catálogo de componentes", "Cada pieza con su vida útil nominal y su instalación."],
  ];

  function fuentes(d) {
    $("fuentes").innerHTML = FUENTES.map(function (f) {
      var m = d.muestras[f[0]];
      return '<article class="fuente"><h3>' + esc(f[1]) + ' <span class="hint">' + num(m.filas) + " filas</span></h3><p>" + esc(f[2]) +
        '</p><div class="table-scroll"><table class="mini"><thead><tr>' + m.columnas.map(function (c) { return "<th>" + esc(c) + "</th>"; }).join("") +
        "</tr></thead><tbody>" + m.ejemplo.map(function (r) {
          return "<tr>" + m.columnas.map(function (c) { return "<td>" + esc(r[c]) + "</td>"; }).join("") + "</tr>";
        }).join("") + "</tbody></table></div></article>";
    }).join("");
  }

  function embudo(d) {
    var s = d.resumen;
    var etapas = [
      [num(s.eventos), "detenciones en el año"],
      [num(s.relevantes), "duran " + s.duracion_minima_min + " minutos o más"],
      [num(s.fallas), "son fallas atribuibles a mantenimiento, con su componente"],
    ];
    $("embudo").innerHTML = etapas.map(function (e, i) {
      return (i ? '<span class="flecha" aria-hidden="true">→</span>' : "") + '<div class="etapa"><span class="valor">' + e[0] +
        '</span><span class="rotulo">' + esc(e[1]) + "</span></div>";
    }).join("");
    var cats = s.por_categoria;
    var max = Math.max.apply(null, Object.keys(cats).map(function (k) { return cats[k]; }));
    var mantencion = ["falla_mecanica", "falla_electrica", "falla_instrumentacion", "fuga", "sobrecalentamiento"];
    $("barras-categorias").innerHTML = Object.keys(cats).map(function (k) {
      var clase = k === "no_clasificado" ? "revision" : mantencion.indexOf(k) >= 0 ? "mantencion" : "otra";
      return '<div class="barra ' + clase + '"><span class="nombre">' + esc(s.nombres_categorias[k] || k) + '</span><span class="pista"><span style="width:' +
        Math.max(1, 100 * cats[k] / max).toFixed(1) + '%"></span></span><span class="n">' + num(cats[k]) + "</span></div>";
    }).join("") + '<p class="hint leyenda"><span class="punto mantencion"></span> atribuible a mantenimiento · <span class="punto otra"></span> operación o causa externa · <span class="punto revision"></span> a revisión</p>';
    $("nota-revision").innerHTML = "<strong>" + num(s.no_clasificados) + " eventos</strong> no traen texto suficiente para clasificarlos con certeza. " +
      "Son solo <strong>" + d.textos_en_revision + " frases distintas</strong>: se revisan una vez cada una, a mano o con un LLM local opcional, y la taxonomía aprende para la próxima.";
  }

  function preguntas(d) {
    var s = d.resumen.brechas_por_regla;
    var e = d.ejemplos;
    var post = d.post_por_ejecutor;
    var lider = Object.keys(post)[0];
    var tarjetas = [
      ["¿Se hizo lo que el plan decía?", s.mantencion_no_ejecutada_o_atrasada, "mantenciones fuera de plan",
        d.subtipos_ejecucion.atrasada + " atrasadas más de 7 días y " + d.subtipos_ejecucion.no_ejecutada + " que nunca se ejecutaron.",
        e.atrasada, "Una mantención atrasada es un riesgo que nadie decidió correr."],
      ["¿La mantención resolvió el problema?", s.falla_post_mantencion, "fallas a 15 días o menos de una mantención",
        post[lider] + " de " + s.falla_post_mantencion + " ocurrieron después de una OT de " + lider + ".",
        e.falla_post_mantencion, "Es la señal más directa para conversar la calidad de ejecución con cada contratista."],
      ["¿Estamos cambiando piezas que aún servían?", s.recambio_redundante, "recambios con menos del 60% de la vida usada",
        "Piezas cambiadas por calendario, sin ninguna falla desde la anterior.",
        e.recambio_redundante, "Cada recambio de más es repuesto, horas hombre y una detención programada que se podría evitar."],
      ["¿Las piezas duran lo que dice el fabricante?", s.falla_antes_vida_util, "fallas antes de la vida útil nominal",
        "Se concentran en pocos tipos de componente: ahí el plan está confiando de más.",
        e.falla_antes_vida_util, "Indica dónde conviene inspeccionar más seguido o pasar a recambio preventivo."],
    ];
    $("preguntas").innerHTML = tarjetas.map(function (t) {
      return '<article class="pregunta"><h3>' + esc(t[0]) + '</h3><p class="cifra"><span class="valor">' + num(t[1]) + '</span> ' + esc(t[2]) +
        "</p><p>" + esc(t[3]) + '</p><p class="ejemplo"><span class="etiqueta">Ejemplo · ' + esc(t[4].componente_id) + " · " + fecha(t[4].fecha) +
        "</span>" + esc(t[4].detalle) + '</p><p class="para-usted">' + esc(t[5]) + "</p></article>";
    }).join("");
  }

  function cambios(d) {
    var s = d.resumen;
    var c = d.cambios_por_tipo;
    $("resumen-cambios").innerHTML = "El plan ajustado sale <strong>en el mismo formato que tu plan</strong>, con <strong>" + s.cambios_plan +
      " cambios</strong>: " + (c["modificar:recambio_redundante"] || 0) + " recambios que se espacian, " + (c["modificar:falla_antes_vida_util"] || 0) +
      " inspecciones que se acortan y " + (c["agregar:falla_antes_vida_util"] || 0) + " recambios preventivos nuevos. Cada uno trae la regla y la evidencia que lo justifica.";
    var titulos = { "recambio_redundante": "Espaciar un recambio", "falla_antes_vida_util": "Inspeccionar más seguido" };
    $("antes-despues").innerHTML = d.cambios_ejemplo.map(function (x) {
      var titulo = x.accion === "agregar" ? "Agregar un recambio preventivo" : titulos[x.regla];
      var antes = x.accion === "agregar" ? "Corre hasta fallar" : "Cada " + x.valor_anterior + " días";
      var despues = x.accion === "agregar" ? x.valor_nuevo.replace(/^recambio cada (\d+) días desde (\S+)$/, function (_, n, f) { return "Recambio cada " + n + " días"; }) : "Cada " + x.valor_nuevo + " días";
      return '<article class="cambio"><h3>' + esc(titulo) + ' <span class="hint">' + esc(x.tarea_id) + " · " + esc(x.componente_id) +
        '</span></h3><div class="ad"><span class="antes">' + esc(antes) + '</span><span class="flecha" aria-hidden="true">→</span><span class="despues">' +
        esc(despues) + '</span></div><p class="hint">' + esc(x.justificacion) + "</p></article>";
    }).join("");
    var filas = d.vida_util.slice().sort(function (a, b) { return a.vida_ajustada_dias / a.vida_nominal_dias - b.vida_ajustada_dias / b.vida_nominal_dias; });
    $("tabla-vida-recorrido").innerHTML = '<thead><tr><th>Tipo de componente</th><th class="num">Fabricante (días)</th><th class="num">Fallas observadas</th>' +
      '<th class="num">Referencia para el plan</th><th class="num">Diferencia</th></tr></thead><tbody>' + filas.map(function (v) {
        var dif = v.vida_ajustada_dias / v.vida_nominal_dias - 1;
        return "<tr><td>" + esc(v.tipo_componente.replace("_", " ")) + '</td><td class="num">' + num(v.vida_nominal_dias) + '</td><td class="num">' + v.fallas +
          '</td><td class="num">' + num(Math.round(v.vida_ajustada_dias)) + '</td><td class="num ' + (dif < -0.05 ? "malo" : "") + '">' +
          (dif > 0 ? "+" : "") + Math.round(dif * 100) + "%</td></tr>";
      }).join("") + "</tbody>";
    $("prioritarios").innerHTML = d.prioritarios.map(function (o) {
      return "<li><strong>" + esc(o.componente_id) + "</strong> · " + esc(o.tipo_componente.replace("_", " ")) + " · " + esc(o.equipo_id) +
        ' <span class="hint">— ' + esc(o.observacion) + "</span></li>";
    }).join("");
  }

  document.addEventListener("DOMContentLoaded", function () {
    fetch("data/demo.json").then(function (r) {
      if (!r.ok) throw new Error("demo.json");
      return r.json();
    }).then(function (d) {
      fuentes(d);
      embudo(d);
      preguntas(d);
      cambios(d);
    }).catch(function () {
      $("fuentes").innerHTML = '<p class="hint">No se pudo cargar el ejemplo. Use «Analizar la planta de ejemplo» más abajo.</p>';
    });
  });
})();
