from datetime import datetime
from unittest import mock

import requests

from viajes import bencina

from .base import ConCache, RespuestaFalsa, api_falsa, cargar_muestra


def estacion_por_id(datos, id_):
    return next(e for e in datos.estaciones if e["id"] == id_)


class NormalizacionTests(ConCache):
    def setUp(self):
        super().setUp()
        muestra = cargar_muestra()
        self.estaciones, self.descartados = bencina.normalizar_respuesta(muestra["estaciones"], muestra["marcas"])
        self.por_id = {e["id"]: e for e in self.estaciones}

    def test_coordenadas_con_coma_y_espacios(self):
        e = self.por_id[400]  # latitud '-32,873774', longitud ' -71,2423'
        self.assertEqual((e["lat"], e["lon"]), (-32.873774, -71.2423))

    def test_isla_de_pascua_es_valida(self):
        self.assertIsNotNone(self.por_id[363]["lat"])

    def test_coordenadas_invalidas_quedan_en_none(self):
        for lat, lon in [("", ""), (None, "-70"), ("0", "0"), ("abc", "-70"), ("-33", "70"), ("33", "-70")]:
            self.assertEqual(bencina.normalizar_coordenadas(lat, lon), (None, None), (lat, lon))

    def test_precios_absurdos_se_descartan(self):
        self.assertNotIn("93", self.por_id[909]["precios"])  # 99999.999
        self.assertEqual(self.por_id[2136]["precios"], {})  # 1.000 en los tres
        self.assertNotIn("93", self.por_id[2263]["precios"])  # precio vacío
        self.assertGreaterEqual(self.descartados["precio_invalido"], 5)

    def test_93_y_a93_se_unen_y_gana_el_mas_barato(self):
        p = self.por_id[29]["precios"]["93"]  # 93: 1586 autoservicio, A93: 1578 asistido
        self.assertEqual((p["precio"], p["atencion"]), (1578.0, "Asistido"))

    def test_precios_desactualizados_se_descartan(self):
        # estación 1519: 93 del 22-oct (1630) y A93 del 4-jun (1635, 145 días)
        p = self.por_id[1519]["precios"]["93"]
        self.assertEqual(p["precio"], 1630.0)
        self.assertGreaterEqual(self.descartados["precio_desactualizado"], 3)

    def test_limite_de_antiguedad(self):
        def estacion(fecha):
            return {"id": 1, "combustibles": [{"nombre_corto": "93", "precio": "1500", "precio_fecha": fecha}]}

        ahora = datetime(2026, 10, 27, 12, 0)
        for fecha, vigente in [("2026-09-27 12:00:00", True), ("2026-09-26 11:00:00", False), ("", True), (None, True)]:
            d = {}
            e = bencina.normalizar_estacion(estacion(fecha), {}, d, ahora)
            self.assertEqual("93" in e["precios"], vigente, fecha)

    def test_solo_93_95_97(self):
        for e in self.estaciones:
            self.assertLessEqual(set(e["precios"]), {"93", "95", "97"})

    def test_fecha_del_precio_y_fecha_ausente(self):
        self.assertEqual(self.por_id[400]["precios"]["93"]["fecha"], "2026-10-22 12:20:54")
        e = bencina.normalizar_estacion(
            {"id": 1, "combustibles": [{"nombre_corto": "93", "precio": "1500", "precio_fecha": None}]}, {}
        )
        self.assertIsNone(e["precios"]["93"]["fecha"])

    def test_marca_por_id_y_sin_marca(self):
        self.assertIn(self.por_id[29]["marca"], {"COPEC", "SHELL", "ARAMCO", "Sin Bandera"})
        e = bencina.normalizar_estacion({"id": 1, "marca": 999, "combustibles": []}, {1: "X"})
        self.assertEqual(e["marca"], "Sin marca")

    def test_estacion_malformada(self):
        descartados = {}
        for malo in (None, "texto", {}, {"id": None}, []):
            self.assertIsNone(bencina.normalizar_estacion(malo, {}, descartados))
        self.assertEqual(descartados["estacion_invalida"], 5)

    def test_respuestas_inutilizables(self):
        for malo in (None, [], {}, {"data": []}, {"data": "x"}, {"data": [None, 3]}):
            with self.assertRaises(ValueError):
                bencina.normalizar_respuesta(malo)


class FiltroTests(ConCache):
    def setUp(self):
        super().setUp()
        muestra = cargar_muestra()
        self.estaciones, _ = bencina.normalizar_respuesta(muestra["estaciones"], muestra["marcas"])

    def test_comuna_sin_tildes_ni_mayusculas(self):
        self.assertEqual({e["comuna"] for e in bencina.filtrar_estaciones(self.estaciones, comuna="valparaiso")}, {"Valparaíso"})

    def test_comuna_exacta_tiene_prioridad(self):
        r = bencina.filtrar_estaciones(self.estaciones, comuna="Arica")
        self.assertTrue(r and all(e["comuna"] == "Arica" for e in r))

    def test_region_y_texto(self):
        self.assertTrue(all("Magallanes" in e["region"] for e in bencina.filtrar_estaciones(self.estaciones, region="magallanes")))
        self.assertTrue(bencina.filtrar_estaciones(self.estaciones, texto="provid"))
        self.assertEqual(bencina.filtrar_estaciones(self.estaciones, comuna="Atlantida"), [])

    def test_sin_filtros_devuelve_todo(self):
        self.assertEqual(len(bencina.filtrar_estaciones(self.estaciones)), len(self.estaciones))


class ObtenerDatosTests(ConCache):
    def test_api_ok_y_cache(self):
        with mock.patch("viajes.bencina.requests.get", side_effect=api_falsa()) as get:
            d1 = bencina.obtener_datos()
            d2 = bencina.obtener_datos()
        self.assertTrue(d1.ok)
        self.assertEqual((d1.fuente, d1.aviso), ("api", ""))
        self.assertIsNotNone(d1.consultado)
        self.assertEqual(get.call_count, 2)  # estaciones + marcas, una sola vez gracias a la caché
        self.assertEqual((d1.estaciones, d1.consultado), (d2.estaciones, d2.consultado))

    def test_forzar_consulta_ignora_cache(self):
        with mock.patch("viajes.bencina.requests.get", side_effect=api_falsa()) as get:
            bencina.obtener_datos()
            bencina.obtener_datos(forzar=True)
        self.assertEqual(get.call_count, 4)

    def test_usa_timeout_y_user_agent(self):
        with mock.patch("viajes.bencina.requests.get", side_effect=api_falsa()) as get:
            bencina.obtener_datos()
        kwargs = get.call_args.kwargs
        self.assertEqual(kwargs["timeout"], bencina.TIMEOUT)
        self.assertIn("proyectobencina", kwargs["headers"]["User-Agent"])

    def test_fallos_sin_respaldo_no_rompen(self):
        casos = {
            "timeout": requests.Timeout("lento"),
            "conexion": requests.ConnectionError("sin red"),
            "http": RespuestaFalsa(status=503),
            "json": RespuestaFalsa(json_invalido=True),
            "vacia": RespuestaFalsa({"data": []}),
        }
        for nombre, caso in casos.items():
            cache = bencina.cache
            cache.clear()
            efecto = caso if isinstance(caso, Exception) else (lambda *a, _c=caso, **k: _c)
            with self.subTest(nombre), mock.patch("viajes.bencina.requests.get", side_effect=efecto):
                d = bencina.obtener_datos()
            self.assertFalse(d.ok)
            self.assertEqual(d.estaciones, [])
            self.assertIn("No hay precios guardados", d.aviso)

    def test_tras_un_fallo_no_se_reintenta_de_inmediato(self):
        with mock.patch("viajes.bencina.requests.get", side_effect=requests.Timeout()) as get:
            bencina.obtener_datos()
            bencina.obtener_datos()
        self.assertEqual(get.call_count, 1)

    def test_falla_pero_hay_respaldo(self):
        with mock.patch("viajes.bencina.requests.get", side_effect=api_falsa()):
            bueno = bencina.obtener_datos()
        bencina.cache.delete(bencina.K_FRESCO)  # la caché fresca venció, el respaldo sigue
        with mock.patch("viajes.bencina.requests.get", side_effect=requests.Timeout()):
            d = bencina.obtener_datos()
        self.assertTrue(d.ok)
        self.assertEqual(d.fuente, "respaldo")
        self.assertEqual(d.consultado, bueno.consultado)
        self.assertIn("últimos precios obtenidos", d.aviso)

    def test_si_falla_solo_marcas_igual_funciona(self):
        base = api_falsa()

        def get(url, **kw):
            if url.endswith("/marca_ciudadano"):
                raise requests.Timeout()
            return base(url, **kw)

        with mock.patch("viajes.bencina.requests.get", side_effect=get):
            d = bencina.obtener_datos()
        self.assertTrue(d.ok)
        self.assertTrue(all(e["marca"] == "Sin marca" for e in d.estaciones))

    def test_archivo_local(self):
        from .base import MUESTRA

        with mock.patch("viajes.bencina.ARCHIVO_LOCAL", str(MUESTRA)), mock.patch("viajes.bencina.requests.get") as get:
            d = bencina.obtener_datos()
        self.assertEqual(d.fuente, "archivo")
        self.assertTrue(d.ok)
        get.assert_not_called()

    def test_archivo_local_inexistente(self):
        with mock.patch("viajes.bencina.ARCHIVO_LOCAL", "/no/existe.json"):
            d = bencina.obtener_datos()
        self.assertFalse(d.ok)
        self.assertIn("archivo local", d.aviso)


class CasosLimiteApiTests(ConCache):
    def est(self, id_, precio="1500"):
        return {"id": id_, "combustibles": [{"nombre_corto": "93", "precio": precio, "precio_fecha": "2026-10-26 10:00:00"}]}

    def test_estaciones_duplicadas_se_cuentan_una_vez(self):
        data = {"data": [self.est(1, "1500"), self.est(1, "1400"), self.est(2)]}
        estaciones, descartados = bencina.normalizar_respuesta(data, None)
        self.assertEqual([e["id"] for e in estaciones], [1, 2])
        self.assertEqual(estaciones[0]["precios"]["93"]["precio"], 1500.0)  # se conserva la primera
        self.assertEqual(descartados["estacion_duplicada"], 1)

    def test_respuestas_inutilizables(self):
        for malo in (None, [], {}, {"data": None}, {"data": []}, {"data": [None, 5, "x", {"sin_id": 1}]}):
            with self.assertRaises(ValueError):
                bencina.normalizar_respuesta(malo, None)

    def test_precios_raros(self):
        for valor, ok in [("1500", True), ("1500,5", True), (" 1500 ", True), (1500, True), ("", False), (None, False),
                          ("abc", False), ("nan", False), ("inf", False), (0, False), (-5, False), (99999, False), (True, False)]:
            e = bencina.normalizar_estacion(self.est(1, valor), {}, None, None)
            self.assertEqual("93" in e["precios"], ok, valor)

    def test_marcas_con_formato_inesperado(self):
        for marcas in (None, [], {"data": "x"}, {"data": [1, None]}):
            estaciones, _ = bencina.normalizar_respuesta({"data": [self.est(1)]}, marcas)
            self.assertEqual(estaciones[0]["marca"], "Sin marca")

    def test_filtros_combinados_sin_resultados_y_con_tildes(self):
        estaciones, _ = bencina.normalizar_respuesta(
            {"data": [dict(self.est(1), comuna="Ñuñoa", region="Metropolitana", direccion="Av. Irarrázaval 1"),
                      dict(self.est(2), comuna="Providencia", region="Metropolitana", direccion="Av. Italia 2")]}, None)
        self.assertEqual(len(bencina.filtrar_estaciones(estaciones, comuna="nunoa")), 1)
        self.assertEqual(len(bencina.filtrar_estaciones(estaciones, texto="IRARRAZAVAL", region="metropolitana")), 1)
        self.assertEqual(bencina.filtrar_estaciones(estaciones, comuna="nunoa", texto="italia"), [])
        self.assertEqual(bencina.filtrar_estaciones(estaciones, region="Biobío"), [])


class DiagnosticoDeFallosTests(ConCache):
    def pedir(self, resp):
        with mock.patch("viajes.bencina.requests.get", return_value=resp), self.assertLogs("viajes.bencina", "WARNING") as logs:
            return bencina.obtener_datos(forzar=True), "\n".join(logs.output)

    def test_http_403_indica_codigo_y_url_y_queda_en_el_registro(self):
        r = RespuestaFalsa(None, status=403)
        r.text, r.headers, r.url = "<html>Access denied</html>", {"Content-Type": "text/html"}, "https://x/api/busqueda_estacion_filtro"
        d, log = self.pedir(r)
        self.assertFalse(d.ok)
        self.assertIn("HTTP 403", d.aviso)
        self.assertIn("HTTP 403", log)
        self.assertIn("Access denied", log)

    def test_respuesta_no_json_muestra_que_llego(self):
        r = RespuestaFalsa(None, json_invalido=True)
        r.text, r.headers = "<html>mantenimiento</html>", {"Content-Type": "text/html"}
        d, log = self.pedir(r)
        self.assertIn("text/html", d.aviso)
        self.assertIn("mantenimiento", log)

    def test_el_fallo_no_impide_recuperarse_despues(self):
        with mock.patch("viajes.bencina.requests.get", return_value=RespuestaFalsa(None, status=500)):
            self.assertFalse(bencina.obtener_datos().ok)
        with mock.patch("viajes.bencina.requests.get", side_effect=api_falsa()):
            self.assertFalse(bencina.obtener_datos().ok)  # dentro del tiempo de espera no se insiste
            self.assertTrue(bencina.obtener_datos(forzar=True).ok)  # y forzar sí consulta de nuevo
            self.assertTrue(bencina.obtener_datos().ok)  # lo recuperado queda en caché


class CertificadoTlsTests(ConCache):
    def test_certificado_vencido_se_explica_y_no_se_oculta(self):
        err = requests.exceptions.SSLError("certificate verify failed: certificate has expired")
        with mock.patch("viajes.bencina.requests.get", side_effect=err):
            d = bencina.obtener_datos(forzar=True)
        self.assertFalse(d.ok)
        self.assertIn("certificado TLS", d.aviso)
        self.assertIn("certificate has expired", d.aviso)
        self.assertIn("BENCINA_VERIFICAR_TLS", d.aviso)

    def test_por_defecto_se_verifica_y_desactivarlo_avisa(self):
        with mock.patch("viajes.bencina.requests.get", side_effect=api_falsa()) as get:
            d = bencina.obtener_datos(forzar=True)
        self.assertTrue(get.call_args.kwargs["verify"])
        self.assertEqual(d.aviso, "")
        bencina.cache.clear()
        with mock.patch("viajes.bencina.VERIFICAR_TLS", False), mock.patch("viajes.bencina.requests.get", side_effect=api_falsa()) as get:
            d = bencina.obtener_datos(forzar=True)
        self.assertFalse(get.call_args.kwargs["verify"])
        self.assertIn("sin verificar", d.aviso)
        self.assertTrue(d.ok)
