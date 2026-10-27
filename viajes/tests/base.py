import json
from datetime import datetime
from pathlib import Path
from unittest import mock

import requests
from django.core.cache import cache
from django.test import SimpleTestCase

MUESTRA = Path(__file__).parent / "fixtures" / "muestra_api.json"
AHORA = datetime(2026, 10, 27, 12, 0)  # la muestra es del 22 al 26 de octubre de 2026


def cargar_muestra():
    """Muestra real (snapshot del 26-oct-2026 de Bencina en Línea) con casos límite."""
    return json.loads(MUESTRA.read_text(encoding="utf-8"))


class RespuestaFalsa:
    def __init__(self, datos=None, status=200, json_invalido=False):
        self._datos, self.status_code, self._json_invalido = datos, status, json_invalido

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        if self._json_invalido:
            raise ValueError("no es JSON")
        return self._datos


def api_falsa(muestra=None):
    """Reemplazo de requests.get que responde como la API de Bencina en Línea."""
    muestra = muestra or cargar_muestra()

    def get(url, **kwargs):
        if url.endswith("/busqueda_estacion_filtro"):
            return RespuestaFalsa(muestra["estaciones"])
        if url.endswith("/marca_ciudadano"):
            return RespuestaFalsa(muestra["marcas"])
        raise AssertionError(f"URL inesperada: {url}")

    return get


class ConCache(SimpleTestCase):
    """Cada prueba parte con la caché vacía y sin archivo local."""

    def setUp(self):
        cache.clear()
        parche = mock.patch("viajes.bencina.ARCHIVO_LOCAL", "")
        parche.start()
        self.addCleanup(parche.stop)
        reloj = mock.patch("viajes.bencina.ahora", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        self.addCleanup(cache.clear)
