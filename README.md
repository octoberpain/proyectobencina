# Recomendador de combustible (Equipo 2 «Los Árabes», IWG400)

Aplicación web en Django que usa **precios reales de bencinas en Chile** (Bencina en Línea, CNE) para:

- **Recomendar el combustible** (93, 95 o 97) más conveniente para un auto del catálogo, con costo por km, gasto mensual, estación más barata y fecha del precio.
- **Calcular el costo de un repostaje** (litros × precio por litro).
- **Mapa interactivo** (Leaflet + OpenStreetMap) con ~1.800 estaciones (según el día), coloreadas por precio del combustible elegido, con filtros por región, comuna y texto (marca o dirección).

## Requisitos

- Python 3.11 o superior (probado con 3.13).
- Dependencias: `Django` y `requests` (ver `requirements.txt`).
- Conexión a internet para obtener los precios y cargar el mapa (Leaflet y los tiles vienen de `unpkg.com` y `server.arcgisonline.com`).

No hay base de datos que configurar ni credenciales: la API de precios es pública y no usa token.

## Ejecutar en local

Desde la carpeta que contiene `manage.py` (en PowerShell):

```powershell
python -m pip install -r requirements.txt
python manage.py runserver
```

Abrir <http://127.0.0.1:8000/>. (Django avisará de migraciones sin aplicar: se puede ignorar, la app no usa base de datos.)

Opcional: crear antes un entorno virtual con `python -m venv venv` y activarlo con `venv\Scripts\activate`.

## Datos de prueba

| Caso | Entrada | Resultado esperado |
|---|---|---|
| 1. Principal | Vehículo `Kia Soluto 1.4`, `800` km/mes, comuna vacía | Recomienda bencina **93** y muestra costo por km, gasto mensual, estación más barata y fecha del precio. |
| 2. Alternativo | Vehículo `Tesla` (o un `km` con texto como `abc`) | Mensaje de error claro («No encontramos ese vehículo…» / «Los km al mes deben ser un número…»). |
| 3. Sin estaciones | Comuna `Atlantida` | «No hay estaciones en la comuna…». |
| Mapa | Elegir región `Magallanes…` o escribir `Providencia` en Comuna | El mapa y la lista «Las más baratas» se actualizan; el texto sobre el mapa indica «N estaciones (de TOTAL)». |

Los precios cambian cada día, por eso los resultados no traen cifras fijas.

## Sin internet o para una demostración estable

`BENCINA_JSON_LOCAL` hace que la app lea un archivo en vez de la API. Se incluye una muestra real (35 estaciones, 22 al 26 de octubre de 2026):

```powershell
$env:BENCINA_JSON_LOCAL = "viajes\tests\fixtures\muestra_api.json"
python manage.py runserver
```

La página avisa «archivo local» para no pasar esos datos por actuales. Sin conexión a internet el mapa no carga (Leaflet y tiles son externos), pero el recomendador sí.

## Cómo se manejan los datos

- `viajes/bencina.py` consulta y normaliza la API; `viajes/views.py` solo usa el resultado.
- **Caché de 1 hora** en memoria. Si la API falla, se muestran los últimos datos buenos (hasta 7 días) con un aviso, y no se reintenta durante 60 s. Sin datos guardados, la página muestra el error y sigue funcionando (la calculadora de repostaje no depende de la API).
- Se descartan precios fuera de $500–$2.500/L y precios con más de 30 días; las coordenadas con coma decimal se interpretan y las que caen fuera de Chile se ignoran (esa estación queda en la lista, sin marcador). «A93» (asistido) y «93» (autoservicio) se juntan en un solo combustible, con el precio más bajo.
- Cada estación se identifica por su `id` de la fuente; precios, dirección y coordenadas siempre salen del mismo registro (no se cruzan por nombre).

Variables de entorno opcionales:

| Variable | Por defecto | Para qué |
|---|---|---|
| `BENCINA_API_BASE` | `https://api.bencinaenlinea.cl/api` | URL base de la API |
| `BENCINA_TIMEOUT` | `15` | Segundos de espera por consulta |
| `BENCINA_CACHE_SEGUNDOS` | `3600` | Duración de la caché |
| `BENCINA_MAX_DIAS` | `30` | Antigüedad máxima de un precio |
| `BENCINA_JSON_LOCAL` | vacío | Leer un archivo en vez de la API |

## Uso de IA

El código se desarrolló con ayuda de Claude (Anthropic) y, para reunir datos de rendimiento de autos, con una segunda IA de búsqueda. Lo declaramos aquí para que se pueda revisar con transparencia.

| Qué hizo la IA | Qué definió, pidió y verificó el equipo |
|---|---|
| Escribió y modificó el código de Django, el normalizador de la API (`viajes/bencina.py`), el mapa (`mapa.js`) y las pruebas automáticas. | Definió qué debe hacer la aplicación y pidió los cambios: quitar altitud, latitud y tipo de camino porque no cambiaban qué combustible conviene, y justificar según el octanaje que recomienda el fabricante para cuidar el motor. |
| Propuso integrar Bencina en Línea y evaluó otras fuentes (ver «Fuentes evaluadas»). | Pidió usar datos reales en vez de cargarlos a mano, el buscador de vehículos, la calculadora de repostaje, el mapa y los filtros. |
| Redactó este README. | Probó la aplicación en su computador y reportó los errores, por ejemplo el bloqueo de los mosaicos del mapa, que se corrigió cambiando de proveedor. |

Cómo se verificó el trabajo de la IA: 54 pruebas automáticas (`python manage.py test`), una prueba en navegador con una muestra real de 1.810 estaciones, la ejecución local con datos en vivo y la revisión de que el costo por km (precio ÷ rendimiento) coincide con el cálculo a mano. Hay límites que seguimos sin resolver y están en «Limitaciones conocidas»: el octanaje del fabricante solo está cargado para un modelo y no todos los rendimientos del catálogo están verificados.

## Pruebas

```powershell
python manage.py test
```

54 pruebas (normalización, caché, errores de red, recomendador, calculadora, filtros y endpoint del mapa). Usan una muestra real guardada en `viajes/tests/fixtures/`, no consultan internet.

## Fuentes evaluadas

| Fuente | Estado | Motivo |
|---|---|---|
| API de Bencina en Línea (CNE) | **Integrada** | Precios, fecha, tipo de atención y coordenadas por estación, sin token. |
| [diland9/precios-combustibles-chile](https://github.com/diland9/precios-combustibles-chile) (MIT) | Solo referencia | Confirma los endpoints y los rangos de precio. Su historial por estación empieza el 1-oct-2026. Se usó su snapshot del 26-oct para probar el normalizador con 1.810 estaciones reales; no se copió su código. |
| API de la CNE (`api.cne.cl` / `api.tramites.cne.cl`) | No integrada | No se pudo consultar desde el entorno de desarrollo. `api.cne.cl` declara acceso gratuito con registro. Bencina en Línea es la plataforma de la CNE, así que probablemente ofrece los mismos datos, y hoy no falta ninguno que justifique agregarla. Si se integra, la credencial debe ir en una variable de entorno. |
| Overpass / OpenStreetMap | No integrada | Las 1.810 estaciones del snapshot traen coordenadas válidas, no hay nada que completar. OSM aporta solo los datos del mapa base. |

## Limitaciones conocidas

- **La API en vivo no pudo probarse desde el entorno donde se desarrolló** (acceso de red restringido). Se validó contra una muestra y un snapshot reales, pero la primera ejecución con internet en tu computador es la verificación real. Si falla, la página lo indica y usa los últimos datos guardados.
- **Catálogo de autos (33 modelos):** el rendimiento viene de Consumo Vehicular, de los fabricantes o de Autocosmos (la fuente se muestra en cada resultado) y no todos están verificados. El **octanaje del fabricante solo está cargado para el Kia Soluto**; para el resto se recomienda el más barato y se avisa.
- El mapa base es de Esri (World Street Map, con atribución, sin API key). Se descartaron `tile.openstreetmap.org` (bloqueó los mosaicos con 403 en pruebas locales) y CARTO (exige API key). Para un sitio con mucho tráfico habría que revisar las condiciones de uso del proveedor.
- `SECRET_KEY` y `DEBUG` son de desarrollo (`config/settings.py`). Para un despliegue público hay que cambiarlos.
