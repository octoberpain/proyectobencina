// Formularios de la página: selector Marca/Modelo y envío sin recargar.
(function () {
  "use strict";

  // --- 1. Vehículo: marca y modelo (se escribe o se elige), o búsqueda manual ---
  var datos = document.getElementById("catalogo-marcas");
  var texto = document.getElementById("vehiculo-texto");
  var inMarca = document.getElementById("sel-marca");
  var inModelo = document.getElementById("sel-modelo");
  var dlMarcas = document.getElementById("dl-marcas");
  var dlModelos = document.getElementById("dl-modelos");
  var lista = document.getElementById("vehiculo-lista");
  var interruptor = document.getElementById("modo-vehiculo");

  function norm(t) {
    return String(t).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
  }

  if (datos && texto && inMarca && inModelo && dlMarcas && dlModelos && lista && interruptor) {
    var marcas = JSON.parse(datos.textContent); // { marca: [[nombre completo, modelo], ...] }
    var nombresMarca = Object.keys(marcas);

    nombresMarca.forEach(function (m) {
      dlMarcas.appendChild(new Option(m, m));
    });

    // La marca escrita: coincidencia exacta, o única que empieza igual ("toy" -> Toyota).
    function marcaEscrita() {
      var q = norm(inMarca.value);
      if (!q) return null;
      var exacta = nombresMarca.filter(function (m) { return norm(m) === q; });
      if (exacta.length === 1) return exacta[0];
      var parecidas = nombresMarca.filter(function (m) { return norm(m).indexOf(q) === 0; });
      return parecidas.length === 1 ? parecidas[0] : null;
    }

    function llenarModelos(marca) {
      dlModelos.innerHTML = "";
      (marcas[marca] || []).forEach(function (par) {
        dlModelos.appendChild(new Option(par[1], par[1]));
      });
      inModelo.disabled = !marca;
      if (!marca) inModelo.value = "";
    }

    // Deja en el campo "vehiculo" (el que se envía) lo que corresponda a lo escrito.
    function actualizarVehiculo() {
      var marca = marcaEscrita();
      var q = norm(inModelo.value);
      if (marca && q) {
        var modelos = marcas[marca];
        var hallados = modelos.filter(function (par) { return norm(par[1]) === q; });
        if (!hallados.length) hallados = modelos.filter(function (par) { return norm(par[1]).indexOf(q) === 0; });
        if (hallados.length === 1) { texto.value = hallados[0][0]; return; }
      }
      // Sin coincidencia clara: se envía lo escrito para que el mensaje de error diga qué falta.
      texto.value = ((marca || inMarca.value) + " " + inModelo.value).trim();
    }

    function buscarEnCatalogo(nombre) {
      var q = norm(nombre);
      for (var m in marcas) {
        for (var i = 0; i < marcas[m].length; i++) {
          if (norm(marcas[m][i][0]) === q) return { marca: m, modelo: marcas[m][i][1], nombre: marcas[m][i][0] };
        }
      }
      return null;
    }

    function modo(nuevo) {
      var esLista = nuevo === "lista";
      interruptor.querySelectorAll("button").forEach(function (b) {
        var activo = b.dataset.modo === nuevo;
        b.classList.toggle("activo", activo);
        b.setAttribute("aria-pressed", activo ? "true" : "false");
      });
      lista.hidden = !esLista;
      texto.hidden = esLista;
      if (esLista) {
        var hallado = buscarEnCatalogo(texto.value);
        inMarca.value = hallado ? hallado.marca : "";
        llenarModelos(hallado ? hallado.marca : null);
        inModelo.value = hallado ? hallado.modelo : "";
        if (!hallado) texto.value = "";
      }
    }

    inMarca.addEventListener("input", function () {
      var marca = marcaEscrita();
      llenarModelos(marca);
      actualizarVehiculo();
    });
    inModelo.addEventListener("input", actualizarVehiculo);
    interruptor.addEventListener("click", function (e) {
      var b = e.target.closest("button[data-modo]");
      if (b) modo(b.dataset.modo);
    });

    interruptor.hidden = false;
    var inicial = texto.value.trim();
    modo(inicial && !buscarEnCatalogo(inicial) ? "manual" : "lista");
  }

  // --- 2. Enviar cada formulario sin recargar la página ---
  // Solo se reemplaza el resultado de ese formulario; lo que el otro tenía queda como estaba.
  document.querySelectorAll("form[data-ajax]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var destino = document.querySelector(form.dataset.ajax);
      var boton = form.querySelector("button[type=submit]");
      if (!destino) { form.submit(); return; }
      if (boton) boton.disabled = true;
      destino.classList.add("cargando");

      fetch(form.action || window.location.href, { method: "POST", body: new FormData(form) })
        .then(function (r) {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.text();
        })
        .then(function (html) {
          var nuevo = new DOMParser().parseFromString(html, "text/html").querySelector(form.dataset.ajax);
          if (!nuevo) throw new Error("sin resultado");
          destino.replaceWith(nuevo);
          nuevo.scrollIntoView({ behavior: "smooth", block: "nearest" });
        })
        .catch(function () {
          form.submit(); // si algo falla, envío normal (recarga la página)
        })
        .then(function () {
          if (boton) boton.disabled = false;
          destino.classList.remove("cargando");
        });
    });
  });
})();
