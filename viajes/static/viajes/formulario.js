// Formularios de la página: selector Marca/Modelo y envío sin recargar.
(function () {
  "use strict";

  // --- 1. Vehículo: elegir marca y modelo, o buscar escribiendo ---
  var datos = document.getElementById("catalogo-marcas");
  var texto = document.getElementById("vehiculo-texto");
  var selMarca = document.getElementById("sel-marca");
  var selModelo = document.getElementById("sel-modelo");
  var lista = document.getElementById("vehiculo-lista");
  var interruptor = document.getElementById("modo-vehiculo");

  if (datos && texto && selMarca && selModelo && lista && interruptor) {
    var marcas = JSON.parse(datos.textContent); // { marca: [[nombre completo, modelo], ...] }

    Object.keys(marcas).forEach(function (m) {
      selMarca.appendChild(new Option(m, m));
    });

    function llenarModelos(marca) {
      selModelo.length = 1; // deja solo "Modelo"
      (marcas[marca] || []).forEach(function (par) {
        selModelo.appendChild(new Option(par[1], par[0]));
      });
      selModelo.disabled = !marca;
    }

    function buscarEnCatalogo(nombre) {
      var buscado = nombre.trim().toLowerCase();
      for (var m in marcas) {
        for (var i = 0; i < marcas[m].length; i++) {
          if (marcas[m][i][0].toLowerCase() === buscado) return { marca: m, nombre: marcas[m][i][0] };
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
        // El campo de texto es lo que se envía: debe coincidir con lo elegido en los selectores.
        var hallado = buscarEnCatalogo(texto.value);
        selMarca.value = hallado ? hallado.marca : "";
        llenarModelos(selMarca.value);
        if (hallado) selModelo.value = hallado.nombre;
        else texto.value = "";
      }
    }

    selMarca.addEventListener("change", function () {
      llenarModelos(selMarca.value);
      texto.value = "";
    });
    selModelo.addEventListener("change", function () {
      texto.value = selModelo.value;
    });
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
