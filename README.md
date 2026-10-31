# Bencuenta · Recomendador de combustible (Equipo 2 «Los Árabes», IWG400)

**Bencuenta** es una aplicación web en Django que usa **precios reales de bencinas en Chile** (Bencina en Línea, CNE) para decidir qué combustible conviene y cuánto se gasta. «Los Árabes» es el nombre del equipo; la página se llama Bencuenta.

## Funcionalidades

- **Recomendador de combustible.** Se elige el vehículo, los km al mes y, opcionalmente, una comuna. La app calcula para cada combustible (93, 95 y 97) el **costo por km = precio por litro ÷ rendimiento del auto** y el **gasto mensual = costo por km × km al mes**, usando la estación más barata de cada combustible (en la comuna indicada o en todo Chile). Recomienda el más barato **que cumpla el octanaje que pide el fabricante**; muestra el costo por km, el gasto mensual, la estación más barata con la fecha de su precio, todas las opciones ordenadas por costo/km y una explicación de por qué se recomienda ese combustible.
- **Selección del vehículo.** Dos modos: «Marca y modelo» (se escribe o se elige de una lista que sugiere opciones) y «Escribir» (búsqueda libre del nombre completo; si hay varios parecidos, el mensaje los lista). Sin JavaScript queda el campo de texto.
- **Catálogo de autos.** 33 modelos «de Chile» y cerca de 2.000 modelos referenciales de otros mercados (ver «Catálogo ampliado»). Cada resultado indica la fuente del rendimiento.
- **Calculadora de repostaje.** Litros × precio por litro = costo total (litros entre 1 y 500; precio entre 1 y 10.000). No depende de la API.
- **Mapa de estaciones** (Leaflet, mapa base de Esri). Muestra cada estación con coordenadas válidas, coloreada según el precio del combustible elegido (93, 95 o 97): verde, amarillo y rojo dividen las estaciones con precio en tres tramos de igual cantidad, y gris es «sin precio informado». La leyenda indica los rangos en pesos. Al tocar una estación se abre un globo con su dirección y los precios 93/95/97 con fecha y tipo de atención.
- **Filtros del mapa.** Región, comuna (con sugerencias), búsqueda por marca o dirección, botones 93/95/97, «Limpiar» y «Centrar mapa». La lista «Las más baratas» (hasta 15 estaciones) acompaña al mapa y al elegir una estación el mapa se centra en ella y abre su globo.
- **Ventana «Fuentes»** (menú superior): lista de dónde sale cada dato. Los mensajes de la página indican además la fecha de consulta, si se usan datos guardados o un archivo local y cuántos precios se descartaron.

### Diseño de la interfaz

- Estilo cálido en crema y verde, con tarjetas redondeadas, iconos coherentes y tipografías alojadas en el proyecto; adaptado a escritorio, tablet y móvil.
- Animaciones sutiles: botones que reaccionan al cursor y al clic, resultados y tarjetas de la lista que aparecen suavemente, indicadores de carga (en el botón al enviar y en el mapa mientras llegan las estaciones), la estación elegida queda resaltada y la ventana de fuentes se abre con una transición.
- **Fondo del encabezado:** carrusel horizontal automático con fotos panorámicas de Chile (Santiago, San Pedro de Atacama, Cordillera de la Sal, Valle de la Luna, Torres del Paine, Carretera Austral, Valparaíso, Pucón, Lago Llanquihue y Viña del Mar). El título va abajo a la izquierda sobre un degradado que sube desde el borde inferior (el paisaje queda limpio arriba) y las tarjetas se montan sobre el borde de la foto. Cada 8 segundos la foto se desliza lentamente a la siguiente, con un zoom muy suave mientras permanece, y la fila es continua, sin saltos. Un pie arriba a la derecha indica el lugar y enlaza a la página de la foto.
- **Calidad de las fotos:** solo se muestran las que cargan, miden al menos 1.100 px de ancho, son panorámicas (no verticales ni casi cuadradas, para que no se vean estiradas) y no son demasiado oscuras. Si ninguna cumple, el encabezado queda liso. Las fotos no están en el repositorio: se cargan desde Wikimedia Commons (enlaces, autores y licencias en la ventana «Fuentes»).
- Se respeta la preferencia de **movimiento reducido** del sistema: con ella activada no hay animaciones ni desplazamiento suave, y el fondo se queda en la primera foto.

## Tecnologías

| Parte | Tecnología |
|---|---|
| Servidor | Python y Django (plantillas y vistas; sin base de datos); `requests` para consultar la API |
| Datos de precios | API pública de Bencina en Línea (CNE), sin token |
| Interfaz | HTML, CSS propio (`estilos.css`, con variables de diseño) y JavaScript sin frameworks |
| Mapa | Leaflet 1.9.4 (desde `unpkg.com`) y mapa base Esri World Street Map (`server.arcgisonline.com`) |
| Fotos del encabezado | Wikimedia Commons (enlazadas, no incluidas en el proyecto) |
| Tipografías e iconos | Nunito y Fraunces (archivos `.woff2` en el proyecto); iconos Lucide (sprite SVG en `_iconos.html`) |
| Pruebas | `unittest` de Django |

## Estructura

| Archivo | Qué hace |
|---|---|
| `viajes/bencina.py` | Consulta, normaliza y guarda en caché los datos de la API; filtra estaciones |
| `viajes/views.py` | Catálogo de autos, búsqueda de vehículos, cálculo de la recomendación, calculadora de repostaje y el endpoint `/estaciones.json` del mapa |
| `viajes/templates/viajes/inicio.html` | Página completa (se sirve en `/`); `_iconos.html` guarda los iconos |
| `viajes/static/viajes/estilos.css` | Todos los estilos y animaciones |
| `viajes/static/viajes/formulario.js` | Selector de marca/modelo, envío de cada formulario sin recargar, ventana de fuentes y carrusel de fotos del encabezado |
| `viajes/static/viajes/mapa.js` | Mapa, marcadores, leyenda, filtros y lista de estaciones |
| `viajes/data/catalogo_referencial.csv` | Modelos referenciales de otros mercados |
| `viajes/tests/` | Pruebas automáticas y la muestra real de la API |

Cada formulario se envía con JavaScript y solo reemplaza su propio resultado, de modo que calcular un repostaje no borra la recomendación. Si JavaScript falla, el envío normal recarga la página y sigue funcionando.

## Requisitos

- Python 3.11 o superior (probado con 3.13).
- Dependencias: `Django` y `requests` (ver `requirements.txt`).
- Conexión a internet para obtener los precios y cargar el mapa (Leaflet viene de `unpkg.com` y los mosaicos de `server.arcgisonline.com`). Las tipografías e iconos van incluidos en el proyecto.

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

La página avisa «archivo local» para no pasar esos datos por actuales. Sin conexión a internet el mapa no carga (Leaflet y los mosaicos son externos), pero el recomendador sí.

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

El código y la documentación se desarrollaron con ayuda de Claude (Anthropic) y, para reunir datos de rendimiento de autos, con una segunda IA de búsqueda. Lo declaramos aquí para que se pueda revisar con transparencia. Todas las funcionalidades y decisiones de diseño fueron dirigidas por el equipo; la IA las implementó. El equipo revisó y probó cada etapa antes de aceptarla.

**Por qué el historial de GitHub muestra a Claude como autor de casi todos los commits.** El proyecto se trabajó primero como borrador en Visual Studio (app Django, vista inicial y plantilla `inicio.html` con el diseño del equipo) y no estaba publicado en GitHub. Los commits se hicieron al subirlo y mejorarlo por etapas con Claude (precios reales, mapa, filtros, pruebas), y por eso figuran a su nombre. Que aparezcan en pocos commits no refleja el trabajo previo ni las decisiones del equipo.

| Qué hizo la IA | Qué definió, pidió y verificó el equipo |
|---|---|
| Escribió y modificó el código de Django, el normalizador de la API (`viajes/bencina.py`), el mapa (`mapa.js`) y las pruebas automáticas, y revisó el código existente para eliminar contradicciones y errores pequeños antes de publicarlo. | Definió qué debe hacer la aplicación y pidió los cambios: quitar altitud, latitud y tipo de camino porque no cambiaban qué combustible conviene, y justificar según el octanaje que recomienda el fabricante para cuidar el motor. |
| Propuso integrar Bencina en Línea y evaluó otras fuentes (ver «Fuentes evaluadas»). | Pidió usar datos reales en vez de cargarlos a mano, el buscador de vehículos, la calculadora de repostaje, el mapa y los filtros. |
| | Probó la aplicación en su computador y reportó los errores, por ejemplo el bloqueo de los mosaicos del mapa, que se corrigió cambiando de proveedor. |

Cómo se verificó el trabajo de la IA: 67 pruebas automáticas (`python manage.py test`), una prueba en navegador con una muestra real de 1.810 estaciones, la ejecución local con datos en vivo y la revisión de que el costo por km (precio ÷ rendimiento) coincide con el cálculo a mano. Hay límites que seguimos sin resolver y están en «Limitaciones conocidas»: el octanaje del fabricante solo está cargado para un modelo y no todos los rendimientos del catálogo están verificados.

## Pruebas

```powershell
python manage.py test
```

67 pruebas (normalización, selector de marca y modelo, catálogo referencial, caché, errores de red, recomendador, calculadora, filtros y endpoint del mapa). Usan una muestra real guardada en `viajes/tests/fixtures/`, no consultan internet.

## Catálogo ampliado (datos referenciales)

Además de los 33 modelos de `AUTOS` (en `views.py`), la app carga `viajes/data/catalogo_referencial.csv` (~2.000 modelos). Salen de datos públicos de **otros mercados**, no de autos vendidos en Chile:

| Origen | Qué es | Límite |
|---|---|---|
| Canadá (NRCan, 2019–2026) | Consumo combinado (mediana entre versiones); gasolina regular o premium | Ciclo de prueba norteamericano. Mismo nombre no implica mismo motor que en Chile. |
| México (CONUEE, 2023) | Catálogo de Rendimientos, solo algunas marcas | Convertido desde PDF; se dejaron fuera las marcas con nombres de versión confusos. |
| Brasil (Inmetro PBEV, 2024) | Consumo con gasolina | La gasolina brasileña lleva etanol: el rendimiento es menor que en Chile. |

Cómo se usan:
- Los 33 modelos originales tienen prioridad: un modelo referencial nunca los reemplaza.
- En pantalla, un resultado con estos datos lleva la etiqueta **«Dato referencial · origen»** y un aviso en la justificación. Son una estimación del rendimiento.
- **No se conoce su octanaje**: se recomienda el combustible más barato y se avisa que no está verificado. Si la fuente canadiense marca el modelo como premium, la justificación lo advierte («confirma en el manual»), pero esa estimación no se usa para elegir el combustible.
- Quedan fuera diésel, eléctricos y enchufables. Los híbridos no enchufables sí están (cargan solo bencina). Algunos modelos casi iguales pueden aparecer dos veces con distinto nombre de versión.
- Atribución: los datos de Canadá contienen información de Natural Resources Canada publicada bajo la Open Government Licence – Canada; los de México son de la CONUEE y los de Brasil del programa PBE Veicular (Inmetro).

## Fuentes evaluadas

| Fuente | Estado | Motivo |
|---|---|---|
| API de Bencina en Línea (CNE) | **Integrada** | Precios, fecha, tipo de atención y coordenadas por estación, sin token. |
| [diland9/precios-combustibles-chile](https://github.com/diland9/precios-combustibles-chile) (MIT) | Solo referencia | Confirma los endpoints y los rangos de precio. Su historial por estación empieza el 1-oct-2026. Se usó su snapshot del 26-oct para probar el normalizador con 1.810 estaciones reales; no se copió su código. |
| API de la CNE (`api.cne.cl` / `api.tramites.cne.cl`) | No integrada | No se pudo consultar desde el entorno de desarrollo. `api.cne.cl` declara acceso gratuito con registro. Bencina en Línea es la plataforma de la CNE, así que probablemente ofrece los mismos datos, y hoy no falta ninguno que justifique agregarla. Si se integra, la credencial debe ir en una variable de entorno. |
| Overpass / OpenStreetMap | No integrada | Las 1.810 estaciones del snapshot traen coordenadas válidas, no hay nada que completar. OSM aporta solo los datos del mapa base. |

## Limitaciones conocidas

- **La API en vivo no pudo probarse desde el entorno donde se desarrolló** (acceso de red restringido). Se validó contra una muestra y un snapshot reales, pero la primera ejecución con internet en tu computador es la verificación real. Si falla, la página lo indica y usa los últimos datos guardados.
- **Catálogo de autos:** son 33 modelos «de Chile» (rendimiento de Consumo Vehicular, de los fabricantes o de Autocosmos; la fuente se muestra en cada resultado; no todos están verificados) más ~2.000 modelos **referenciales** de otros mercados (ver «Catálogo ampliado»). El **octanaje del fabricante solo está cargado para el Kia Soluto**; para el resto se recomienda el más barato y se avisa.
- El mapa base es de Esri (World Street Map, con atribución, sin API key). Se descartaron `tile.openstreetmap.org` (bloqueó los mosaicos con 403 en pruebas locales) y CARTO (exige API key). Para un sitio con mucho tráfico habría que revisar las condiciones de uso del proveedor.
- La lista junto al mapa muestra solo las 15 estaciones más baratas del filtro actual; el mapa dibuja todas las que tienen coordenadas.
- Las fotos del encabezado se enlazan desde Wikimedia Commons y no se pudieron abrir desde el entorno de desarrollo: el carrusel y sus filtros de calidad se probaron con imágenes de prueba. Hay que revisar en el navegador que carguen y que sean las deseadas (el código descarta las que fallen, sean pequeñas, verticales u oscuras).
- Leaflet se carga desde un CDN: sin internet el mapa no aparece (el recomendador y la calculadora sí funcionan).
- Las animaciones y la apariencia se probaron en Chromium; no se probó en otros navegadores.
- `SECRET_KEY` y `DEBUG` son de desarrollo (`config/settings.py`). Para un despliegue público hay que cambiarlos.
