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
