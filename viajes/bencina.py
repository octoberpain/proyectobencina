"""Consulta y normalización de precios de Bencina en Línea (CNE).

API pública sin token: GET {API_BASE}/busqueda_estacion_filtro y /marca_ciudadano.
Formato de salida de cada estación (el mismo para cualquier fuente):

    {"id", "marca", "region", "comuna", "direccion", "lat", "lon",
     "precios": {"93": {"precio": 1586.0, "fecha": "2026-10-01 08:45:00", "atencion": "AutoServicio"}}}

`lat`/`lon` son None si la fuente no trae coordenadas válidas; `precios` solo incluye los
precios 93/95/97 que pasaron la validación (los demás se consideran "sin dato").
"""
import json
import logging
import os
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache

import requests
import urllib3
from django.core.cache import cache
from django.utils import timezone

log = logging.getLogger(__name__)

API_BASE = os.environ.get("BENCINA_API_BASE", "https://api.bencinaenlinea.cl/api")
TIMEOUT = float(os.environ.get("BENCINA_TIMEOUT", "15"))
CACHE_SEGUNDOS = int(os.environ.get("BENCINA_CACHE_SEGUNDOS", "3600"))  # datos "frescos"
RESPALDO_SEGUNDOS = 7 * 24 * 3600  # si la API falla, se muestran los últimos datos buenos
REINTENTO_SEGUNDOS = 60  # tras un fallo no se vuelve a consultar durante este tiempo
ARCHIVO_LOCAL = os.environ.get("BENCINA_JSON_LOCAL", "")  # JSON con el formato de la muestra
# Verificación del certificado TLS de la API. Solo se desactiva a propósito (BENCINA_VERIFICAR_TLS=0), por ejemplo si el
# certificado del servidor está vencido; mientras tanto la página avisa que la conexión no está verificada.
VERIFICAR_TLS = os.environ.get("BENCINA_VERIFICAR_TLS", "1") != "0"
USER_AGENT = "proyectobencina/1.0 (proyecto universitario USM; uso ciudadano)"

COMBUSTIBLES = ("93", "95", "97")
RANGO_PRECIO = (500, 2500)  # $/L; fuera de este rango se descarta (ceros, 99999, etc.)
MAX_DIAS = int(os.environ.get("BENCINA_MAX_DIAS", "30"))  # precios más antiguos no se usan
RANGO_LAT = (-56.5, -17.0)  # Chile (incluye Isla de Pascua e Isla Robinson Crusoe)
RANGO_LON = (-110.0, -66.0)

if not VERIFICAR_TLS:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    log.warning("BENCINA_VERIFICAR_TLS=0: las consultas a la API no verifican el certificado TLS.")

K_FRESCO, K_RESPALDO, K_ERROR = "bencina:fresco", "bencina:respaldo", "bencina:error"


@dataclass
class Datos:
    estaciones: list = field(default_factory=list)
    fuente: str = "error"  # api | respaldo | archivo | error
    consultado: object = None  # datetime (UTC) de la consulta a la fuente
    aviso: str = ""
    descartados: dict = field(default_factory=dict)

    @property
    def ok(self):
        return bool(self.estaciones)

    @property
    def n_precios_descartados(self):
        return sum(v for k, v in self.descartados.items() if k.startswith("precio"))


# ---------- normalización ----------
def ahora():
    """Hora actual (UTC, sin zona). Aparte para poder fijarla en las pruebas."""
    return timezone.now().replace(tzinfo=None)


def parsear_fecha(texto):
    try:
        return datetime.fromisoformat(str(texto).strip()).replace(tzinfo=None)
    except ValueError:
        return None


@lru_cache(maxsize=8192)
def normalizar_texto(texto):
    """Minúsculas y sin tildes, para comparar nombres de comunas/estaciones."""
    s = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower().strip()


def a_float(valor):
    """Acepta número o texto (con coma decimal y espacios). None si no es válido."""
    if isinstance(valor, bool) or valor is None:
        return None
    try:
        n = float(str(valor).strip().replace(",", "."))
    except ValueError:
        return None
    return n if n == n and n not in (float("inf"), float("-inf")) else None


def normalizar_coordenadas(lat, lon):
    la, lo = a_float(lat), a_float(lon)
    if la is None or lo is None:
        return None, None
    if not (RANGO_LAT[0] <= la <= RANGO_LAT[1] and RANGO_LON[0] <= lo <= RANGO_LON[1]):
        return None, None
    return la, lo


def grupo_combustible(nombre_corto):
    """'A93' (asistido) y '93' (autoservicio) son el mismo combustible: '93'."""
    c = str(nombre_corto or "").strip().upper()
    c = c[1:] if c.startswith("A") and c[1:] in COMBUSTIBLES else c
    return c if c in COMBUSTIBLES else None


def normalizar_estacion(raw, marcas, descartados=None, ahora_=None):
    """Convierte una estación cruda de la API al formato común; None si no sirve."""
    descartados = descartados if descartados is not None else {}
    if not isinstance(raw, dict) or raw.get("id") is None:
        descartados["estacion_invalida"] = descartados.get("estacion_invalida", 0) + 1
        return None

    precios = {}
    for c in raw.get("combustibles") or []:
        if not isinstance(c, dict):
            continue
        grupo = grupo_combustible(c.get("nombre_corto"))
        if not grupo:
            continue
        precio = a_float(c.get("precio"))
        if precio is None or not (RANGO_PRECIO[0] <= precio <= RANGO_PRECIO[1]):
            descartados["precio_invalido"] = descartados.get("precio_invalido", 0) + 1
            continue
        fecha = parsear_fecha(c.get("precio_fecha"))
        if fecha and ahora_ and (ahora_ - fecha).days > MAX_DIAS:  # sin fecha: no se puede saber, se conserva
            descartados["precio_desactualizado"] = descartados.get("precio_desactualizado", 0) + 1
            continue
        actual = precios.get(grupo)
        if actual is None or precio < actual["precio"]:  # 93 vs A93: se conserva el más barato
            precios[grupo] = {
                "precio": precio,
                "fecha": (str(c.get("precio_fecha")).strip() or None) if c.get("precio_fecha") else None,
                "atencion": c.get("tipo_atencion_nombre") or "",
            }

    lat, lon = normalizar_coordenadas(raw.get("latitud"), raw.get("longitud"))
    if lat is None:
        descartados["sin_coordenadas"] = descartados.get("sin_coordenadas", 0) + 1

    return {
        "id": raw["id"],
        "marca": marcas.get(raw.get("marca")) or "Sin marca",
        "region": str(raw.get("region") or "").strip(),
        "comuna": str(raw.get("comuna") or "").strip(),
        "direccion": str(raw.get("direccion") or "").strip(),
        "lat": lat,
        "lon": lon,
        "precios": precios,
    }


def normalizar_respuesta(estaciones_json, marcas_json=None, ahora_=None):
    """(estaciones normalizadas, descartados). Lanza ValueError si la respuesta no es usable."""
    data = estaciones_json.get("data") if isinstance(estaciones_json, dict) else None
    if not isinstance(data, list) or not data:
        raise ValueError("La respuesta no trae estaciones.")
    marcas = {}
    if isinstance(marcas_json, dict) and isinstance(marcas_json.get("data"), list):
        marcas = {m.get("id"): m.get("nombre") for m in marcas_json["data"] if isinstance(m, dict)}
    descartados = {}
    ahora_ = ahora_ or ahora()
    estaciones, vistos = [], set()
    for r in data:
        e = normalizar_estacion(r, marcas, descartados, ahora_)
        if not e:
            continue
        clave = (str(e["id"]), e["lat"], e["lon"], e["direccion"])  # solo se descartan filas idénticas repetidas
        if clave in vistos:
            descartados["estacion_duplicada"] = descartados.get("estacion_duplicada", 0) + 1
            continue
        vistos.add(clave)
        estaciones.append(e)
    if not estaciones:
        raise ValueError("Ninguna estación de la respuesta es válida.")
    return estaciones, descartados


# ---------- obtención ----------
def _muestra(resp, n=120):
    """Primeros caracteres de la respuesta, en una línea, para el registro de errores."""
    return " ".join(str(getattr(resp, "text", "") or "")[:n].split())


def _get_json(ruta):
    """GET a la API de Bencina en Línea. Cuando falla, deja en el registro la URL, el código HTTP, el tipo de contenido
    y el comienzo de la respuesta, para poder saber por qué (un bloqueo, una página de error y un cambio de formato se ven distinto)."""
    url = f"{API_BASE}/{ruta}"
    resp = requests.get(
        url, timeout=TIMEOUT, verify=VERIFICAR_TLS, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    tipo = (getattr(resp, "headers", None) or {}).get("Content-Type", "?")
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        log.warning("HTTP %s en %s (content-type %s): %r", resp.status_code, url, tipo, _muestra(resp))
        raise
    try:
        return resp.json()
    except ValueError as e:
        log.warning("Respuesta no JSON en %s (HTTP %s, content-type %s): %r", url, resp.status_code, tipo, _muestra(resp))
        raise ValueError(f"{ruta} no devolvió JSON (HTTP {resp.status_code}, {tipo}): {_muestra(resp, 60)!r}") from e


def _descargar():
    estaciones_json = _get_json("busqueda_estacion_filtro")
    try:
        marcas_json = _get_json("marca_ciudadano")
    except (requests.RequestException, ValueError):  # sin marcas igual sirve: "Sin marca"
        log.warning("No se pudo obtener la lista de marcas.")
        marcas_json = None
    return normalizar_respuesta(estaciones_json, marcas_json)


def _desde_archivo(ruta):
    with open(ruta, encoding="utf-8") as f:
        contenido = json.load(f)
    estaciones, descartados = normalizar_respuesta(contenido.get("estaciones"), contenido.get("marcas"))
    return Datos(estaciones, "archivo", timezone.now(), "Datos de un archivo local, no de la consulta en vivo.", descartados)


def obtener_datos(forzar=False):
    """Estaciones con precios. Nunca lanza excepciones: si todo falla devuelve Datos(ok=False)."""
    if ARCHIVO_LOCAL:
        try:
            return _desde_archivo(ARCHIVO_LOCAL)
        except (OSError, ValueError) as e:
            return Datos(aviso=f"No se pudo leer el archivo local ({e}).")

    if not forzar:
        fresco = cache.get(K_FRESCO)
        if fresco:
            return fresco
        if cache.get(K_ERROR):  # falló hace poco: no insistir en cada carga de la página
            return _respaldo_o_error(cache.get(K_ERROR))

    try:
        estaciones, descartados = _descargar()
    except requests.Timeout as e:
        return _fallo(f"Bencina en Línea no respondió en {TIMEOUT:g} s.", e)
    except requests.exceptions.SSLError as e:
        return _fallo(
            f"No se pudo verificar el certificado TLS de la API ({str(e)[-160:]}). Si el certificado del servidor está vencido o "
            "mal configurado, la API no se puede usar con verificación; BENCINA_VERIFICAR_TLS=0 permite usarla sin verificar.", e)
    except requests.ConnectionError as e:
        return _fallo(f"No se pudo conectar con Bencina en Línea ({type(e).__name__}: {str(e)[:150]}).", e)
    except requests.HTTPError as e:
        r = e.response
        return _fallo(f"Bencina en Línea respondió con error HTTP {r.status_code} en {getattr(r, 'url', API_BASE)}.", e)
    except (requests.RequestException, ValueError) as e:  # JSON inválido o respuesta vacía
        return _fallo(f"Bencina en Línea devolvió una respuesta que no se pudo interpretar ({str(e)[:200]}).", e)

    aviso = "" if VERIFICAR_TLS else "Conexión con la API sin verificar el certificado TLS (BENCINA_VERIFICAR_TLS=0)."
    datos = Datos(estaciones, "api", timezone.now(), aviso, descartados)
    cache.set(K_FRESCO, datos, CACHE_SEGUNDOS)
    cache.set(K_RESPALDO, datos, RESPALDO_SEGUNDOS)
    cache.delete(K_ERROR)
    return datos


def _fallo(mensaje, excepcion):
    log.warning("%s (%s)", mensaje, excepcion)
    cache.set(K_ERROR, mensaje, REINTENTO_SEGUNDOS)
    return _respaldo_o_error(mensaje)


def _respaldo_o_error(mensaje):
    respaldo = cache.get(K_RESPALDO)
    if respaldo:
        return Datos(
            respaldo.estaciones, "respaldo", respaldo.consultado,
            f"{mensaje} Se muestran los últimos precios obtenidos.", respaldo.descartados,
        )
    return Datos(aviso=f"{mensaje} No hay precios guardados para mostrar.")


# ---------- filtros ----------
def filtrar_estaciones(estaciones, comuna="", region="", texto=""):
    """Filtra por comuna, región y texto libre (marca, dirección o comuna), sin importar tildes.

    La comuna coincide exacta si existe una con ese nombre; si no, por texto contenido.
    """
    c, r, t = normalizar_texto(comuna), normalizar_texto(region), normalizar_texto(texto)
    if c:
        exactas = [e for e in estaciones if normalizar_texto(e["comuna"]) == c]
        estaciones = exactas or [e for e in estaciones if c in normalizar_texto(e["comuna"])]
    if r:
        estaciones = [e for e in estaciones if r in normalizar_texto(e["region"])]
    if t:
        estaciones = [
            e for e in estaciones if t in normalizar_texto(f"{e['marca']} {e['direccion']} {e['comuna']}")
        ]
    return list(estaciones)
