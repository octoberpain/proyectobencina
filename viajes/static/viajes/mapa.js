// Mapa de estaciones (Leaflet + OpenStreetMap). Los datos vienen de /estaciones.json,
// que usa los mismos precios que el recomendador.
(function () {
  "use strict";

  var cfg = document.getElementById("mapa-config");
  var estado = document.getElementById("mapa-estado");
  var fuenteEl = document.getElementById("mapa-fuente");
  var listaEl = document.getElementById("mapa-lista");
  var COLORES = { barato: "#16a34a", medio: "#f59e0b", caro: "#dc2626", sin: "#9ca3af" };
  var COMBUSTIBLES = ["93", "95", "97"];
  var MAX_LISTA = 15;

  if (!cfg || !document.getElementById("mapa")) return;
  if (typeof L === "undefined") {
    estado.textContent = "No se pudo cargar la librería del mapa (Leaflet). Revisa tu conexión a internet.";
    return;
  }

  var fRegion = document.getElementById("f-region");
  var fComuna = document.getElementById("f-comuna");
  var fQ = document.getElementById("f-q");
  var listaComunas = document.getElementById("lista-comunas");
  var tituloLista = document.getElementById("mapa-lista-titulo");
  var combustible = "93";
  var opcionesListas = false;
  var peticion = 0;
  var controlador = null;
  var datos = null;
  var capa = L.layerGroup();
  var marcadores = {};

  var mapa = L.map("mapa", { preferCanvas: true }).setView([-33.45, -70.65], 5);
  // tile.openstreetmap.org (403) y CARTO (exige API key) no sirvieron; el mapa base de Esri funciona sin clave.
  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", {
    maxZoom: 19,
    attribution: "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ, OpenStreetMap contributors",
  }).addTo(mapa);
  capa.addTo(mapa);

  var leyenda = L.control({ position: "bottomright" });
  leyenda.onAdd = function () {
    var div = L.DomUtil.create("div", "mapa-leyenda");
    div.setAttribute("aria-live", "polite");
    this._div = div;
    return div;
  };
  leyenda.addTo(mapa);

  // ---------- utilidades (todo el texto externo entra con textContent, nunca como HTML) ----------
  function el(tag, texto, clase) {
    var e = document.createElement(tag);
    if (texto !== undefined && texto !== null) e.textContent = texto;
    if (clase) e.className = clase;
    return e;
  }
  function clp(n) {
    return "$" + Math.round(n).toLocaleString("es-CL");
  }
  function fechaCorta(f) {
    return f ? f.slice(0, 16) : "sin fecha informada";
  }
  function precioDe(e) {
    return e.precios && e.precios[combustible] ? e.precios[combustible] : null;
  }
  function umbrales(precios) {
    var s = precios.slice().sort(function (a, b) { return a - b; });
    if (!s.length) return [0, 0];
    return [s[Math.floor((s.length - 1) / 3)], s[Math.floor(((s.length - 1) * 2) / 3)]];
  }
  function colorDe(precio, umb) {
    if (precio <= umb[0]) return COLORES.barato;
    if (precio <= umb[1]) return COLORES.medio;
    return COLORES.caro;
  }

  function popup(e) {
    var d = el("div", null, "popup-estacion");
    d.appendChild(el("strong", e.marca));
    d.appendChild(el("div", e.direccion));
    d.appendChild(el("div", e.comuna + (e.region ? ", " + e.region : ""), "popup-sub"));
    var t = el("table", null, "popup-precios");
    COMBUSTIBLES.forEach(function (c) {
      var p = e.precios && e.precios[c];
      var tr = el("tr", null, c === combustible ? "sel" : "");
      tr.appendChild(el("th", c));
      tr.appendChild(el("td", p ? clp(p.precio) + "/L" : "sin precio informado"));
      tr.appendChild(el("td", p ? fechaCorta(p.fecha) + (p.atencion ? " · " + p.atencion : "") : "", "popup-sub"));
      t.appendChild(tr);
    });
    d.appendChild(t);
    return d;
  }

  // ---------- dibujo ----------
  function dibujar(reajustar) {
    capa.clearLayers();
    marcadores = {};
    var estaciones = datos.estaciones;
    var conPrecio = estaciones.filter(function (e) { return precioDe(e); });
    var umb = umbrales(conPrecio.map(function (e) { return precioDe(e).precio; }));
    var puntos = [];
    var sinCoord = 0;

    // Primero las sin precio y las más caras: así las baratas quedan dibujadas encima y se ven.
    var porPrecio = function (e) { var p = precioDe(e); return p ? p.precio : Infinity; };
    estaciones.slice().sort(function (a, b) { return porPrecio(b) - porPrecio(a); }).forEach(function (e) {
      if (e.lat === null || e.lon === null) { sinCoord++; return; }
      var p = precioDe(e);
      var color = p ? colorDe(p.precio, umb) : COLORES.sin;
      var m = L.circleMarker([e.lat, e.lon], {
        radius: p ? 6 : 4, color: "#1f2937", weight: 1, fillColor: color, fillOpacity: p ? 0.9 : 0.6,
      });
      m.bindPopup(function () { return popup(e); });
      m.addTo(capa);
      marcadores[e.id] = m;
      puntos.push([e.lat, e.lon]);
    });

    if (reajustar && puntos.length) mapa.fitBounds(L.latLngBounds(puntos), { padding: [20, 20], maxZoom: 15 });
    dibujarLeyenda(conPrecio.length, umb);
    tituloLista.textContent = "Las más baratas" + (datos.filtrado ? " (según tus filtros)" : " (todo Chile)");
    dibujarLista(conPrecio);

    var msg;
    if (!estaciones.length) msg = datos.filtrado ? "Ninguna estación coincide con los filtros." : "No hay estaciones para mostrar.";
    else if (!puntos.length) msg = "Hay " + estaciones.length + " estaciones, pero ninguna tiene coordenadas válidas para el mapa.";
    else msg = puntos.length + " estaciones en el mapa" + (datos.filtrado ? " (de " + datos.total + ")" : "") + " · " + conPrecio.length + " con precio de bencina " + combustible + " informado.";
    if (sinCoord && puntos.length) msg += " " + sinCoord + " sin coordenadas (solo aparecen en la lista).";
    estado.textContent = msg;
  }

  function dibujarLeyenda(n, umb) {
    var d = leyenda._div;
    d.textContent = "";
    d.appendChild(el("strong", "Bencina " + combustible + " ($/L)"));
    if (n) {
      [["barato", "hasta " + clp(umb[0])], ["medio", clp(umb[0]) + " – " + clp(umb[1])], ["caro", "más de " + clp(umb[1])]].forEach(function (f) {
        var r = el("div");
        var punto = el("span", null, "punto");
        punto.style.background = COLORES[f[0]];
        r.appendChild(punto);
        r.appendChild(document.createTextNode(f[1]));
        d.appendChild(r);
      });
    }
    var r2 = el("div");
    var p2 = el("span", null, "punto");
    p2.style.background = COLORES.sin;
    r2.appendChild(p2);
    r2.appendChild(document.createTextNode("sin precio informado"));
    d.appendChild(r2);
  }

  function dibujarLista(conPrecio) {
    listaEl.textContent = "";
    var orden = conPrecio.slice().sort(function (a, b) { return precioDe(a).precio - precioDe(b).precio || a.id - b.id; });
    if (!orden.length) {
      listaEl.appendChild(el("li", "Ninguna estación tiene precio informado para este combustible.", "lista-vacia"));
      return;
    }
    orden.slice(0, MAX_LISTA).forEach(function (e) {
      var li = el("li");
      var b = el("button", null, "item-estacion");
      b.type = "button";
      b.appendChild(el("span", clp(precioDe(e).precio), "item-precio"));
      b.appendChild(el("span", e.marca, "item-marca"));
      b.appendChild(el("span", e.direccion + ", " + e.comuna, "item-texto item-dir"));
      b.appendChild(el("span", "precio de " + fechaCorta(precioDe(e).fecha), "item-fecha"));
      b.addEventListener("click", function () {
        Array.prototype.forEach.call(listaEl.querySelectorAll(".item-estacion.elegida"), function (x) { x.classList.remove("elegida"); });
        b.classList.add("elegida");  // solo visual: resalta la estación elegida
        var m = marcadores[e.id];
        if (!m) { estado.textContent = "Esta estación no tiene coordenadas, no se puede ubicar en el mapa."; return; }
        mapa.setView(m.getLatLng(), Math.max(mapa.getZoom(), 15));
        m.openPopup();
      });
      li.appendChild(b);
      listaEl.appendChild(li);
    });
  }

  function dibujarFuente() {
    var t = "Fuente: Bencina en Línea (CNE)";
    if (datos.consultado) t += " · consultado " + new Date(datos.consultado).toLocaleString("es-CL");
    if (datos.fuente === "archivo") t += " · archivo local";
    var n = 0;
    Object.keys(datos.descartados || {}).forEach(function (k) { if (k.indexOf("precio") === 0) n += datos.descartados[k]; });
    if (n) t += " · " + n + " precios no se usaron (de hace más de " + datos.max_dias + " días o inválidos)";
    fuenteEl.textContent = t + ".";
    if (datos.aviso) {
      fuenteEl.appendChild(el("span", " ⚠ " + datos.aviso, "aviso"));
    }
  }

  // ---------- filtros ----------
  function parametros() {
    var p = new URLSearchParams();
    if (fRegion.value) p.set("region", fRegion.value);
    if (fComuna.value.trim()) p.set("comuna", fComuna.value.trim());
    if (fQ.value.trim()) p.set("q", fQ.value.trim());
    return p;
  }
  function hayFiltros() {
    return !!(fRegion.value || fComuna.value.trim() || fQ.value.trim());
  }
  function llenarOpciones() {
    fRegion.length = 1;
    datos.regiones.forEach(function (r) {
      var o = el("option", r);
      o.value = r;
      fRegion.appendChild(o);
    });
    actualizarComunas();
    opcionesListas = true;
  }
  function actualizarComunas() {
    listaComunas.textContent = "";
    datos.comunas.forEach(function (c) {
      if (fRegion.value && c.region !== fRegion.value) return;
      var o = el("option");
      o.value = c.nombre;
      listaComunas.appendChild(o);
    });
  }

  // ---------- carga ----------
  // Solo visual: marca el estado "cargando" para que el CSS muestre el indicador.
  function ocupado(si) {
    estado.classList.toggle("cargando-datos", si);
    listaEl.classList.toggle("cargando-datos", si);
    listaEl.setAttribute("aria-busy", si ? "true" : "false");
  }

  function cargar(reajustar) {
    var mia = ++peticion;
    if (controlador) controlador.abort();
    controlador = new AbortController();
    var ctrl = controlador;
    estado.textContent = "Cargando estaciones…";
    ocupado(true);
    var timer = setTimeout(function () { ctrl.abort(); }, 45000);
    var q = parametros().toString();
    var filtrado = hayFiltros(); // los filtros de ESTA consulta, no lo que se escriba mientras responde
    fetch(cfg.dataset.url + (q ? "?" + q : ""), { signal: ctrl.signal, headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.json().then(
          function (j) { return { ok: r.ok, json: j }; },
          function () { return { ok: false, json: { error: "Respuesta inesperada del servidor." } }; }
        );
      })
      .then(function (res) {
        clearTimeout(timer);
        if (mia !== peticion) return;
        if (!res.ok) throw new Error(res.json.error || "No se pudieron obtener las estaciones.");
        datos = res.json;
        datos.filtrado = filtrado;
        if (!opcionesListas) llenarOpciones();
        dibujarFuente();
        dibujar(reajustar);
        ocupado(false);
      })
      .catch(function (err) {
        clearTimeout(timer);
        if (mia !== peticion) return;
        ocupado(false);
        estado.textContent = err.name === "AbortError" ? "La consulta tardó demasiado. Intenta de nuevo." : err.message;
      });
  }

  var espera = null;
  function recargarPronto() {
    clearTimeout(espera);
    espera = setTimeout(function () { cargar(true); }, 350);
  }
  document.getElementById("mapa-filtros").addEventListener("submit", function (e) { e.preventDefault(); cargar(true); });
  fRegion.addEventListener("change", function () { if (datos) actualizarComunas(); fComuna.value = ""; cargar(true); });
  fComuna.addEventListener("input", recargarPronto);
  fQ.addEventListener("input", recargarPronto);
  document.getElementById("f-limpiar").addEventListener("click", function () {
    fRegion.value = ""; fComuna.value = ""; fQ.value = "";
    if (datos) actualizarComunas();
    cargar(true);
  });
  document.getElementById("f-centrar").addEventListener("click", function () {
    var pts = [];
    Object.keys(marcadores).forEach(function (k) { pts.push(marcadores[k].getLatLng()); });
    if (pts.length) mapa.fitBounds(L.latLngBounds(pts), { padding: [20, 20], maxZoom: 15 });
  });

  Array.prototype.forEach.call(document.querySelectorAll("[data-comb]"), function (b) {
    b.addEventListener("click", function () {
      combustible = b.dataset.comb;
      Array.prototype.forEach.call(document.querySelectorAll("[data-comb]"), function (x) {
        var activo = x === b;
        x.classList.toggle("activo", activo);
        x.setAttribute("aria-pressed", activo ? "true" : "false");
      });
      if (datos) dibujar(false);
    });
  });

  cargar(true);
})();
