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
        var opcion = new Option(par[1], par[1]);
        if (par[2]) opcion.label = "referencial";  // dato de otro mercado
        dlModelos.appendChild(opcion);
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
      if (form.dataset.enviando) return;  // ya hay una petición en curso: no se envía dos veces
      form.dataset.enviando = "1";
      if (boton) boton.disabled = true;
      destino.classList.add("cargando");
      var ctrl = new AbortController();
      var limite = setTimeout(function () { ctrl.abort(); }, 45000);  // si el servidor no responde, se cae al envío normal

      fetch(form.action || window.location.href, { method: "POST", body: new FormData(form), signal: ctrl.signal })
        .then(function (r) {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.text();
        })
        .then(function (html) {
          var nuevo = new DOMParser().parseFromString(html, "text/html").querySelector(form.dataset.ajax);
          if (!nuevo) throw new Error("sin resultado");
          destino.replaceWith(nuevo);
          nuevo.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" });
        })
        .catch(function () {
          form.submit(); // si algo falla, envío normal (recarga la página)
        })
        .then(function () {
          clearTimeout(limite);
          delete form.dataset.enviando;
          if (boton) boton.disabled = false;
          destino.classList.remove("cargando");
        });
    });
  });

  // --- 3. Ventana de fuentes consultadas ---
  var ventana = document.getElementById("fuentes");
  var abrir = document.getElementById("abrir-fuentes");
  var cerrar = document.getElementById("cerrar-fuentes");
  if (ventana && abrir && typeof ventana.showModal === "function") {
    abrir.addEventListener("click", function () { ventana.showModal(); });
    cerrar.addEventListener("click", function () { ventana.close(); });
    // clic fuera de la ventana (en el fondo oscuro) también la cierra
    ventana.addEventListener("click", function (e) { if (e.target === ventana) ventana.close(); });
  } else if (abrir) {
    abrir.hidden = true;
  }
  // --- 4. Fondo del encabezado: carrusel horizontal de fotos de Chile ---
  // Las fotos salen de los enlaces de la ventana «Fuentes» (Wikimedia Commons). Nunca hay más de LISTAS en la fila (más las que
  // están en camino): al salir una foto se descarta y se pide la siguiente de la lista, así que no se bajan todas a la vez ni
  // se acumulan. Solo se muestran las que sirven: se omiten las que fallan, tardan demasiado, son pequeñas, verticales u oscuras.
  // Si ninguna sirve, queda el fondo verde (sin el brillo de carga). Con movimiento reducido se pide solo una foto y no hay carrusel.
  (function () {
    var hero = document.getElementById("hero");
    var pista = document.getElementById("carrusel-pista");
    var pie = document.getElementById("hero-pie");
    var lugar = document.getElementById("hero-lugar");
    var credito = document.getElementById("hero-credito");
    var cola = Array.prototype.slice.call(document.querySelectorAll("#fotos-fondo a[data-foto]"));
    if (!hero || !pista || !pie || !lugar || !credito) return;
    if (!cola.length) { hero.classList.add("sin-fotos"); return; }
    hero.classList.add("cargando-fotos");  // el brillo del fondo provisional solo existe mientras de verdad se espera

    var ESPERA = 8000;       // tiempo que se ve cada paisaje
    var DESLIZAR = 1900;     // duración del desplazamiento (lento y suave)
    var PLAZO = 12000;       // máximo que se espera por una foto antes de omitirla
    var LISTAS = 3;          // fotos que se mantienen en la fila (la visible, la siguiente y una de reserva)
    var CLARA = 140;         // brillo medio (0 a 255) desde el cual se refuerza el degradado detrás del texto
    var OSCURA = 45;         // brillo medio bajo el cual la foto se descarta
    // Tamaño de la foto según la pantalla (Wikimedia ofrece 1280 y 1920 px de ancho)
    var ANCHO = window.innerWidth * (window.devicePixelRatio || 1) > 1500 ? 1920 : 1280;
    var ORIGENES = ["50% 55%", "35% 50%", "65% 50%", "50% 40%"];  // hacia dónde "respira" el zoom de cada foto
    var reducido = window.matchMedia("(prefers-reduced-motion: reduce)");
    function escuchar(mq, fn) { if (mq.addEventListener) mq.addEventListener("change", fn); else if (mq.addListener) mq.addListener(fn); }
    var url = function (f) {
      return "https://commons.wikimedia.org/wiki/Special:FilePath/" + encodeURIComponent(f.dataset.foto.replace(/ /g, "_")) + "?width=" + ANCHO;
    };

    // Descarga una foto y decide si sirve. El brillo se mide con un canvas, lo que exige CORS; si el servidor no lo permite
    // se reintenta sin medirlo. Todo el proceso comparte un único plazo. Devuelve los datos de la foto o null.
    function cargar(fuente) {
      return new Promise(function (ok) {
        var limite = Date.now() + PLAZO, img, reloj, cerrado = false;
        function fin(res) {
          if (cerrado) return;
          cerrado = true;
          clearTimeout(reloj);
          if (!res && img) { img.onload = img.onerror = null; img.removeAttribute("src"); }  // corta la descarga pendiente
          ok(res);
        }
        reloj = setTimeout(function () { fin(null); }, PLAZO);

        function intentar(conCors) {
          img = new Image();
          img.decoding = "async";
          img.referrerPolicy = "no-referrer";
          if (conCors) img.crossOrigin = "anonymous";
          img.onerror = function () {
            if (cerrado) return;
            if (conCors && Date.now() < limite - 1500) intentar(false); else fin(null);
          };
          img.onload = function () {
            var w = img.naturalWidth, h = img.naturalHeight, brillo = null;
            if (w < 1100 || w / h < 1.4) return fin(null);  // pixelada, vertical o casi cuadrada: se vería mal
            if (conCors) {
              try {
                var cv = document.createElement("canvas");
                cv.width = 32; cv.height = 18;
                var cx = cv.getContext("2d");
                cx.drawImage(img, 0, 0, 32, 18);
                var px = cx.getImageData(0, 0, 32, 18).data, suma = 0;
                for (var q = 0; q < px.length; q += 4) suma += 0.2126 * px[q] + 0.7152 * px[q + 1] + 0.0722 * px[q + 2];
                brillo = suma / (px.length / 4);
              } catch (e) { brillo = null; /* sin acceso a los píxeles: se acepta */ }
              if (brillo !== null && brillo < OSCURA) return fin(null);
            }
            // Se decodifica antes de mostrarla: así la foto aparece ya lista, sin parpadeos ni cuadros en blanco.
            var listo = function () { fin({ fuente: fuente, img: img, lugar: fuente.dataset.lugar, ficha: fuente.href, brillo: brillo }); };
            if (img.decode) img.decode().then(listo, listo); else listo();
          };
          img.src = url(fuente);
        }
        intentar(true);
      });
    }

    var contador = 0;
    function diapo(foto) {
      var d = document.createElement("div");
      d.className = "diapo";
      d.dataset.lugar = foto.lugar;
      d.dataset.ficha = foto.ficha;
      d.fuente = foto.fuente;  // para volver a ponerla en la lista cuando salga de la fila
      d.dataset.clara = foto.brillo !== null && foto.brillo >= CLARA ? "1" : "";
      foto.img.className = "diapo-img";
      foto.img.alt = "";
      foto.img.draggable = false;
      foto.img.style.transformOrigin = ORIGENES[contador++ % ORIGENES.length];
      d.appendChild(foto.img);
      return d;
    }

    function mostrar(d) {  // lugar, crédito y refuerzo del degradado según la foto que queda visible
      lugar.textContent = d.dataset.lugar;
      credito.href = d.dataset.ficha;
      pie.hidden = false;
      hero.classList.toggle("foto-clara", d.dataset.clara === "1");
    }

    // ---- Carga a demanda: la fila nunca pasa de LISTAS fotos (con movimiento reducido, de una) ----
    var enVuelo = 0;
    function meta() { return reducido.matches ? 1 : LISTAS; }
    function terminarCarga() {  // sin fotos y nada más por probar: el encabezado queda en su versión final, sin brillo de carga
      if (enVuelo || cola.length || pista.children.length) return;
      hero.classList.remove("cargando-fotos");
      hero.classList.add("sin-fotos");
    }
    function llenar() {
      while (enVuelo < 2 && cola.length && pista.children.length + enVuelo < meta()) {
        enVuelo++;
        cargar(cola.shift()).then(function (foto) {
          enVuelo--;
          if (foto && pista.children.length < meta()) aceptar(foto);
          llenar();  // si falló o se omitió, se pasa a la siguiente sin detener nada
          terminarCarga();
        });
      }
      terminarCarga();
    }
    // Si la red va lenta, el brillo no sigue indefinidamente: a los 15 s se detiene (las fotos que lleguen igual se muestran).
    setTimeout(function () { hero.classList.remove("cargando-fotos"); }, 15000);

    // ---- Carrusel ----
    // Dos procesos que deben ir coordinados: el temporizador de la espera (`timer`) y el cierre de cada desplazamiento (`cierre`,
    // que reordena la fila). `moviendo` es verdadero entre el inicio del desplazamiento y su cierre. Si la pestaña se oculta o se
    // activa el movimiento reducido a mitad del desplazamiento, el cierre se hace en el acto (nadie lo está viendo).
    var timer = null, cierre = null, moviendo = false;
    function detener() { clearTimeout(timer); timer = null; }
    function programar() {
      detener();
      if (pista.children.length > 1 && !reducido.matches && !document.hidden && !moviendo) timer = setTimeout(avanzar, ESPERA);
    }
    function avanzar() {
      timer = null;
      if (moviendo || document.hidden || reducido.matches) return;
      if (pista.children.length < 2) return programar();
      moviendo = true;
      pista.style.transition = "transform " + DESLIZAR + "ms cubic-bezier(.45, .05, .2, 1)";
      pista.style.transform = "translateX(-100%)";
      mostrar(pista.children[1]);
      cierre = setTimeout(terminar, DESLIZAR + 60);
    }
    // La foto que ya salió deja la fila (si hay más por mostrar vuelve al final de la lista; si no, al final de la fila) y la
    // pista vuelve a 0 sin transición: el ciclo es continuo y sin saltos.
    function terminar() {
      clearTimeout(cierre);
      cierre = null;
      if (!moviendo) return;
      var salida = pista.firstElementChild;
      pista.style.transition = "none";
      pista.style.transform = "translateX(0)";
      if (cola.length && pista.children.length >= meta() && salida.fuente) {
        pista.removeChild(salida);
        cola.push(salida.fuente);
      } else {
        pista.appendChild(salida);
      }
      void pista.offsetWidth;
      moviendo = false;
      llenar();
      programar();
    }
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) { detener(); if (moviendo) terminar(); } else programar();
    });
    escuchar(reducido, function () {
      if (reducido.matches) { detener(); if (moviendo) terminar(); } else { llenar(); programar(); }
    });

    // Cada foto aceptada entra al final de la fila. La primera que llega ya se muestra; con dos o más empieza el carrusel.
    function aceptar(foto) {
      var d = diapo(foto);
      pista.appendChild(d);
      if (pista.children.length === 1) { mostrar(d); hero.classList.add("con-foto"); hero.classList.remove("cargando-fotos", "sin-fotos"); }
      if (!timer && !moviendo) programar();
    }

    // Se empieza después de que la página terminó de cargar, para no competir con el mapa y los precios.
    function empezar() { llenar(); }
    if (document.readyState === "complete") empezar(); else window.addEventListener("load", empezar);
  })();
})();
