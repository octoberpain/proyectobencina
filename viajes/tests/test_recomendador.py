from unittest import mock

import requests
from django.test import Client

from viajes import bencina, views

from .base import ConCache, api_falsa, cargar_muestra


def estaciones_muestra():
    muestra = cargar_muestra()
    return bencina.normalizar_respuesta(muestra["estaciones"], muestra["marcas"])[0]


def auto(rendimiento=15.0, octanaje=None):
    return {"nombre": "Auto de prueba", "rendimiento": rendimiento, "octanaje_recomendado": octanaje, "fuente": "prueba"}


class BuscarAutoTests(ConCache):
    def test_exacto_parcial_sin_tildes(self):
        self.assertEqual(views.buscar_auto("Kia Soluto 1.4")[0]["nombre"], "Kia Soluto 1.4")
        self.assertEqual(views.buscar_auto("soluto")[0]["nombre"], "Kia Soluto 1.4")
        self.assertEqual(views.buscar_auto("citroen")[0]["nombre"], "Citroën C3 1.2")

    def test_ambiguo_inexistente_y_vacio(self):
        self.assertIn("varios parecidos", views.buscar_auto("suzuki")[1])
        self.assertIn("No encontramos", views.buscar_auto("Tesla")[1])
        self.assertIn("Escribe", views.buscar_auto("  ")[1])


class RecomendarTests(ConCache):
    def setUp(self):
        super().setUp()
        self.estaciones = estaciones_muestra()

    def test_elige_el_precio_mas_bajo_de_cada_combustible(self):
        r = views.recomendar_combustible(auto(15.0), 1000, self.estaciones)
        for o in r["opciones"]:
            minimo = min(e["precios"][o["combustible"]]["precio"] for e in self.estaciones if o["combustible"] in e["precios"])
            self.assertEqual(o["precio"], minimo)
            self.assertAlmostEqual(o["costo_km"], minimo / 15.0)
            self.assertAlmostEqual(o["gasto_mes"], minimo / 15.0 * 1000)

    def test_recomienda_el_mas_barato_si_el_octanaje_no_se_conoce(self):
        r = views.recomendar_combustible(auto(octanaje=None), 1000, self.estaciones)
        self.assertEqual(r["recomendado"], r["opciones"][0])
        self.assertTrue(any("no tenemos verificado" in j for j in r["justificacion"]))

    def test_respeta_el_octanaje_del_fabricante(self):
        r = views.recomendar_combustible(auto(octanaje=97), 1000, self.estaciones)
        self.assertEqual(r["recomendado"]["combustible"], "97")
        self.assertTrue(any("recomienda mínimo 97" in j for j in r["justificacion"]))
        self.assertEqual([o["cumple"] for o in r["opciones"] if o["combustible"] == "93"], [False])

    def test_incluye_estacion_y_fecha_del_precio(self):
        r = views.recomendar_combustible(auto(), 500, self.estaciones)
        rec = r["recomendado"]
        self.assertIn("·", rec["estacion"])
        self.assertTrue(rec["fecha_txt"])

    def test_sin_precios_devuelve_error(self):
        sin_precios = [dict(e, precios={}) for e in self.estaciones]
        self.assertIn("error", views.recomendar_combustible(auto(), 500, sin_precios))
        self.assertIn("error", views.recomendar_combustible(auto(), 500, []))

    def test_desempate_estable(self):
        a = {"id": 2, "marca": "A", "direccion": "x", "comuna": "c", "precios": {"93": {"precio": 1500.0, "fecha": None, "atencion": ""}}}
        b = dict(a, id=1)
        r1 = views.recomendar_combustible(auto(), 1, [a, b])
        r2 = views.recomendar_combustible(auto(), 1, [b, a])
        self.assertEqual(r1["recomendado"]["estacion"], r2["recomendado"]["estacion"])


class VistaTests(ConCache):
    def setUp(self):
        super().setUp()
        self.client = Client()
        parche = mock.patch("viajes.bencina.requests.get", side_effect=api_falsa())
        parche.start()
        self.addCleanup(parche.stop)

    def recomendar(self, **extra):
        datos = {"accion": "recomendar", "vehiculo": "Kia Soluto 1.4", "km_mes": "800,5", "comuna": ""}
        datos.update(extra)
        return self.client.post("/", datos)

    def test_get_funciona_sin_consultar_la_api(self):
        with mock.patch("viajes.bencina.requests.get") as get:
            r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        get.assert_not_called()

    def test_recomendacion_con_precios_reales(self):
        r = self.recomendar()
        self.assertContains(r, "Recomendado para tu Kia Soluto 1.4")
        self.assertContains(r, "Precio informado:")
        self.assertContains(r, "Bencina en Línea (CNE)")
        self.assertEqual(r.context["resultado"]["recomendado"]["combustible"], "93")

    def test_comuna_filtra_las_estaciones(self):
        r = self.recomendar(comuna="punta arenas")
        self.assertEqual(r.context["resultado"]["ambito"], "punta arenas")
        self.assertTrue(all("Punta Arenas" in o["estacion"] for o in r.context["resultado"]["opciones"]))

    def test_comuna_sin_estaciones(self):
        r = self.recomendar(comuna="Atlantida")
        self.assertContains(r, "No hay estaciones en la comuna")
        self.assertNotIn("resultado", r.context)

    def test_api_caida_no_rompe_la_pagina(self):
        with mock.patch("viajes.bencina.requests.get", side_effect=requests.Timeout()):
            r = self.recomendar()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "No hay precios guardados")

    def test_api_caida_con_respaldo_avisa(self):
        self.recomendar()  # llena el respaldo
        bencina.cache.delete(bencina.K_FRESCO)
        with mock.patch("viajes.bencina.requests.get", side_effect=requests.Timeout()):
            r = self.recomendar()
        self.assertContains(r, "últimos precios obtenidos")
        self.assertIsNotNone(r.context["resultado"])

    def test_entradas_invalidas(self):
        r = self.recomendar(vehiculo="Tesla", km_mes="abc")
        self.assertContains(r, "No encontramos ese vehículo")
        self.assertContains(r, "Los km al mes deben ser un número")
        self.assertContains(self.recomendar(km_mes="0"), "entre 1 y 30000")

    def test_calculadora_de_repostaje_sigue_igual(self):
        r = self.client.post("/", {"accion": "repostaje", "litros": "40", "precio_litro": "1350"})
        self.assertContains(r, "$54.000")
        self.assertContains(r, "40 L × $1.350/L")
        r = self.client.post("/", {"accion": "repostaje", "litros": "0", "precio_litro": "x"})
        self.assertContains(r, "Los litros deben ser un número")
        self.assertContains(r, "El precio por litro debe ser un número")


class SelectorMarcaModeloTests(ConCache):
    def test_agrupa_por_marca_y_ordena(self):
        g = views.agrupar_por_marca([("Toyota Yaris 1.5", 1, None, ""), ("Suzuki Swift 1.2 ISG", 1, None, ""), ("Toyota RAV4 2.0 AWD", 1, None, "")])
        self.assertEqual(list(g), ["Suzuki", "Toyota"])
        self.assertEqual(g["Toyota"], [["Toyota RAV4 2.0 AWD", "RAV4 2.0 AWD"], ["Toyota Yaris 1.5", "Yaris 1.5"]])

    def test_todos_los_autos_quedan_en_algun_modelo(self):
        g = views.agrupar_por_marca(views.AUTOS)
        self.assertEqual(sum(len(v) for v in g.values()), len(views.AUTOS))
        self.assertIn("Kia Soluto 1.4", [n for v in g.values() for n, _ in v])

    def test_la_pagina_trae_los_selectores_y_conserva_el_campo_de_texto(self):
        r = Client().get("/")
        self.assertContains(r, 'id="catalogo-marcas"')
        self.assertContains(r, 'id="sel-marca"')
        self.assertContains(r, 'name="vehiculo"')  # sin JavaScript sigue funcionando la búsqueda manual
        self.assertContains(r, 'data-ajax="#resultado-recomendador"')
        self.assertContains(r, 'data-ajax="#resultado-repostaje"')


class EstacionesJsonTests(ConCache):
    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_devuelve_estaciones_con_coordenadas_y_precios(self):
        with mock.patch("viajes.bencina.requests.get", side_effect=api_falsa()):
            r = self.client.get("/estaciones.json")
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertEqual(j["fuente"], "api")
        self.assertEqual(len(j["estaciones"]), 35)
        e = next(x for x in j["estaciones"] if x["id"] == 400)  # coordenadas con coma en la fuente
        self.assertEqual((e["lat"], e["lon"]), (-32.873774, -71.2423))
        self.assertEqual(set(e["precios"]), {"93", "95", "97"})
        self.assertEqual(set(e["precios"]["93"]), {"precio", "fecha", "atencion"})
        self.assertGreaterEqual(j["descartados"]["precio_invalido"], 5)

    def test_estaciones_sin_precio_valido_siguen_en_la_lista(self):
        with mock.patch("viajes.bencina.requests.get", side_effect=api_falsa()):
            j = self.client.get("/estaciones.json").json()
        e = next(x for x in j["estaciones"] if x["id"] == 2136)  # los tres precios eran 1.000
        self.assertEqual(e["precios"], {})
        self.assertIsNotNone(e["lat"])

    def test_error_de_la_fuente_responde_503_con_mensaje(self):
        with mock.patch("viajes.bencina.requests.get", side_effect=requests.Timeout()):
            r = self.client.get("/estaciones.json")
        self.assertEqual(r.status_code, 503)
        self.assertIn("No hay precios guardados", r.json()["error"])
        self.assertEqual(r.json()["estaciones"], [])

    def test_solo_acepta_get(self):
        self.assertEqual(self.client.post("/estaciones.json").status_code, 405)

    def test_la_pagina_incluye_el_mapa(self):
        r = self.client.get("/")
        self.assertContains(r, 'id="mapa"')
        self.assertContains(r, "/estaciones.json")
        self.assertContains(r, "viajes/mapa.js")


class EstacionesJsonFiltrosTests(ConCache):
    """Filtros del mapa: region, comuna y q (valores esperados contados a mano sobre la muestra de 35 estaciones)."""

    def setUp(self):
        super().setUp()
        self.client = Client()

    def pedir(self, **params):
        with mock.patch("viajes.bencina.requests.get", side_effect=api_falsa()):
            r = self.client.get("/estaciones.json", params)
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_sin_filtros_devuelve_todo_y_las_listas_para_los_selectores(self):
        j = self.pedir()
        self.assertEqual((len(j["estaciones"]), j["total"]), (35, 35))
        self.assertEqual(len(j["regiones"]), 8)
        self.assertIn({"nombre": "Quillota", "region": "Valparaíso"}, j["comunas"])
        self.assertEqual(j["max_dias"], 30)

    def test_comuna_sin_importar_tildes_ni_mayusculas(self):
        j = self.pedir(comuna="PROVIDENCIA")
        self.assertEqual(len(j["estaciones"]), 5)
        self.assertEqual({e["comuna"] for e in j["estaciones"]}, {"Providencia"})
        self.assertEqual(j["total"], 35)  # total sigue siendo el del país

    def test_region(self):
        j = self.pedir(region="magallanes")
        self.assertEqual(len(j["estaciones"]), 5)
        self.assertTrue(all("Magallanes" in e["region"] for e in j["estaciones"]))

    def test_texto_libre_por_marca(self):
        j = self.pedir(q="shell")
        self.assertIn(400, {e["id"] for e in j["estaciones"]})
        self.assertTrue(all("SHELL" in e["marca"].upper() for e in j["estaciones"]))

    def test_filtros_combinados(self):
        j = self.pedir(region="Valparaíso", comuna="Quillota")
        self.assertEqual([e["id"] for e in j["estaciones"]], [400])
        self.assertEqual(self.pedir(region="Atacama", comuna="Quillota")["estaciones"], [])

    def test_sin_coincidencias_no_es_un_error(self):
        j = self.pedir(comuna="Atlantida", q="zzzz")
        self.assertEqual((j["estaciones"], j["total"]), ([], 35))

    def test_los_filtros_no_dejan_a_las_estaciones_sin_formato_comun(self):
        e = self.pedir(comuna="Quillota")["estaciones"][0]
        self.assertEqual(set(e), {"id", "marca", "region", "comuna", "direccion", "lat", "lon", "precios"})

    def test_parametros_enormes_o_raros_no_rompen(self):
        self.assertEqual(self.pedir(q="a" * 5000, comuna="<script>")["estaciones"], [])
