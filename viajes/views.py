import csv
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from . import bencina

# --- 1. Datos: (nombre, km/L mixto, octanaje mínimo [None = sin verificar], fuente) ---
# Autocosmos = ficha técnica de autocosmos.cl; "fabricante" = sitio oficial en Chile.
AUTOS = [
    ("Suzuki Swift 1.2 ISG", 22.8, None, "Consumo Vehicular (1.2 ISG MT)"),
    ("Kia Soluto 1.4", 17.5, 93, "Consumo Vehicular (1.4 5MT); octanaje según ficha de Kia Chile"),
    ("Suzuki Fronx 1.5 GL", 19.2, None, "Suzuki Chile (fabricante)"),
    ("Mazda CX-5 2.0", 14.2, None, "Mazda Chile (fabricante)"),
    ("Hyundai Grand i10 HB 1.2", 17.8, None, "Autocosmos (1.2 5MT)"),
    ("Hyundai Accent HB 1.4", 16.9, None, "Autocosmos (1.4 6MT)"),
    ("Hyundai Creta 1.5", 15.2, None, "Autocosmos (1.5 6MT, nota de prensa)"),
    ("Kia Morning 1.0", 20.0, None, "Autocosmos (1.0L EX)"),
    ("Kia Sonet 1.5", 14.5, None, "Autocosmos (1.5L EX)"),
    ("Chevrolet Sail 1.5", 15.0, None, "Autocosmos (1.5 LT)"),
    ("Suzuki Celerio 1.0", 22.8, None, "Autocosmos (1.0L GLX)"),
    ("Suzuki Baleno 1.4", 18.5, None, "Autocosmos (1.4L GLX 2021)"),
    ("Suzuki Alto 1.0", 20.9, None, "Suzuki Chile (fabricante, GL Plus)"),
    ("Suzuki Dzire 1.2", 19.5, None, "Autocosmos (1.2L GL; otra ficha da 19,1)"),
    ("Mazda 3 Sedán 2.0", 15.1, None, "Mazda Chile (fabricante, 6MT)"),
    ("Ford Territory 1.5 EcoBoost", 13.0, None, "Ford Chile (fabricante, ciclo de laboratorio)"),
    ("Toyota Yaris 1.5", 16.9, None, "Toyota Chile (fabricante, Sedán E MT)"),
    ("Toyota Yaris Cross 1.5", 15.4, None, "Toyota Chile (fabricante, Xi MT)"),
    ("Toyota Raize 1.2", 18.9, None, "Toyota Chile (fabricante)"),
    ("Toyota RAV4 2.0 AWD", 13.8, None, "Toyota Chile (fabricante, LE CVT)"),
    ("Subaru Crosstrek 2.0 AWD", 13.9, None, "Subaru Chile (fabricante, CVT)"),
    ("Volkswagen Polo 1.6", 14.9, None, "Autocosmos (1.6 MSi Comfortline)"),
    ("Volkswagen Tera 1.6", 14.3, None, "Autocosmos (nota de prensa, 5MT)"),
    ("MG MG3 1.5", 14.3, None, "Autocosmos (1.5L Std Aut)"),
    ("MG ZX 1.5", 14.7, None, "Autocosmos (1.5L COM)"),
    ("MG ZS 1.5", 14.3, None, "Autocosmos (1.5L Comfort)"),
    ("Changan Alsvin 1.4", 16.2, None, "Autocosmos (Comfort)"),
    ("Chery Tiggo 2 Pro 1.5", 13.1, None, "Autocosmos (1.5L GLS)"),
    ("GWM Jolion 1.5T", 12.6, None, "Autocosmos (1.5T Active)"),
    ("Omoda C5 1.5T", 13.5, None, "Autocosmos (Comfort)"),
    ("Geely Coolray 1.5T", 15.3, None, "Autocosmos (GL Comfort)"),
    ("Peugeot 208 1.2", 17.2, None, "Autocosmos (1.2L Style PureTech)"),
    ("Citroën C3 1.2", 17.4, None, "Autocosmos (1.2L PureTech Live)"),
]
COMBUSTIBLES = ["93", "95", "97"]


# --- 2. Auxiliares ---
def a_numero(texto):
    """Texto a número (acepta coma); None si no es válido."""
    try:
        n = float(str(texto).strip().replace(",", "."))
    except ValueError:
        return None
    if n != n or n in (float("inf"), float("-inf")):
        return None
    return n


def normalizar(texto):
    """Minúsculas y sin tildes, para buscar sin importar cómo se escriba."""
    texto = unicodedata.normalize("NFD", str(texto))
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").lower().strip()


catalogo = {
    normalizar(n): {"nombre": n, "rendimiento": r, "octanaje_recomendado": o, "fuente": f, "referencial": False}
    for n, r, o, f in AUTOS
}

# --- Catálogo ampliado: datos REFERENCIALES de otros mercados (Canadá, México, Brasil) ---
# No son autos chilenos: el motor y la calibración pueden diferir. Los 33 autos de AUTOS tienen
# prioridad y no se pisan. El octanaje de estos autos no se conoce (None): se avisa en pantalla.
ARCHIVO_REFERENCIAL = Path(__file__).resolve().parent / "data" / "catalogo_referencial.csv"
FUENTES_REFERENCIALES = {
    "Canadá": "NRCan Canadá (consumo combinado, ciclo de prueba norteamericano)",
    "México": "CONUEE México (Catálogo de Rendimientos 2023)",
    "Brasil": "Inmetro Brasil PBEV 2024 (la gasolina brasileña lleva etanol: rinde menos que en Chile)",
}
MARCA_DE = {}  # nombre -> marca, para marcas de más de una palabra (Land Rover, Alfa Romeo...)


def cargar_referenciales():
    if not ARCHIVO_REFERENCIAL.exists():
        return
    with open(ARCHIVO_REFERENCIAL, encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            nombre = " ".join(fila["nombre"].split())  # sin espacios dobles
            clave = normalizar(nombre)
            rend = a_numero(fila["rendimiento_km_l"])
            if clave in catalogo or rend is None or rend <= 0:
                continue
            fuente = FUENTES_REFERENCIALES.get(fila["origen"], fila["origen"])
            anios = f", año(s) {fila['anios']}" if fila.get("anios") else ""
            catalogo[clave] = {
                "nombre": nombre, "rendimiento": rend, "octanaje_recomendado": None,
                "fuente": f"{fuente}{anios}", "referencial": True, "origen": fila["origen"],
                "premium": fila.get("premium", ""),  # solo Canadá lo informa: Sí / No / Depende de la versión
            }
            MARCA_DE[nombre] = fila["marca"]


cargar_referenciales()


def agrupar_por_marca(autos):
    """{marca: [[nombre completo, modelo, es_referencial], ...]} para los selectores Marca y Modelo.
    La marca viene de MARCA_DE (marcas de varias palabras) o es la primera palabra del nombre."""
    marcas = {}
    for n, *_ in autos:
        marca = MARCA_DE.get(n) or n.partition(" ")[0]
        modelo = n[len(marca):].strip() if n.startswith(marca) else n.partition(" ")[2]
        referencial = catalogo.get(normalizar(n), {}).get("referencial", False)
        marcas.setdefault(marca, []).append([n, modelo, referencial])
    return {m: sorted(v, key=lambda x: normalizar(x[1])) for m, v in sorted(marcas.items(), key=lambda x: normalizar(x[0]))}


def buscar_auto(texto):
    """Devuelve (auto, error): nombre exacto o una sola coincidencia parcial."""
    q = normalizar(texto)
    if not q:
        return None, "Escribe el nombre del vehículo."
    if q in catalogo:
        return catalogo[q], None
    palabras = q.split()
    coincidencias = [k for k in catalogo if all(p in k for p in palabras)]
    if len(coincidencias) == 1:
        return catalogo[coincidencias[0]], None
    # Los autos de Chile van primero. Si entre las coincidencias hay uno solo de Chile, es ese
    # (igual que antes de ampliar el catálogo); el resultado muestra el nombre exacto elegido.
    coincidencias.sort(key=lambda k: catalogo[k]["referencial"])
    de_chile = [k for k in coincidencias if not catalogo[k]["referencial"]]
    if len(de_chile) == 1:
        return catalogo[de_chile[0]], None
    if coincidencias:
        nombres = ", ".join(catalogo[k]["nombre"] for k in coincidencias[:5])
        return None, f"Hay varios parecidos: {nombres}. Elige uno de la lista."
    return None, "No encontramos ese vehículo en el catálogo."


def clp(x):
    """Pesos enteros con punto de miles. Redondea .5 hacia arriba (round() lo manda al par más cercano)."""
    return "$" + f"{int(x + 0.5):,}".replace(",", ".")


def num(x, max_dec=3):
    """Número con coma decimal y sin ceros sobrantes (40 -> «40», 40.55 -> «40,55»)."""
    t = f"{x:.{max_dec}f}".rstrip("0").rstrip(".")
    return t.replace(".", ",")


def dec(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


# --- 3. Recomendación: costo/km = precio ÷ rendimiento; respeta el octanaje del fabricante ---
def recomendar_combustible(auto, km_mes, estaciones):
    """estaciones: lista en el formato de bencina.py (precios por combustible con fecha)."""
    opciones = []

    for comb in COMBUSTIBLES:
        ofertas = [(est["precios"][comb]["precio"], str(est["id"]), est) for est in estaciones if comb in est["precios"]]
        if ofertas:
            precio, _, est = min(ofertas, key=lambda o: (o[0], o[1]))
            costo_km = precio / auto["rendimiento"]
            opciones.append({
                "combustible": comb,
                "precio": precio,
                "estacion": f"{est['marca']} · {est['direccion']}, {est['comuna']}",
                "fecha": est["precios"][comb]["fecha"],
                "costo_km": costo_km,
                "gasto_mes": costo_km * km_mes,
                "cumple": auto["octanaje_recomendado"] is None or int(comb) >= auto["octanaje_recomendado"],
            })

    if not opciones:
        return {"error": "No hay precios."}

    opciones.sort(key=lambda o: o["costo_km"])

    barato = opciones[0]
    aptas = [o for o in opciones if o["cumple"]]
    recomendado = aptas[0] if aptas else barato

    # Justificación
    oct_rec = auto["octanaje_recomendado"]
    just = [
        f"Costo estimado: ${dec(recomendado['costo_km'])} por km "
        f"(precio más bajo encontrado ÷ rendimiento de {dec(auto['rendimiento'])} km/L).",
        f"Fuente del rendimiento: {auto['fuente']}.",
    ]
    if auto.get("referencial"):
        just.append(
            f"Dato referencial: el rendimiento de este modelo viene de datos de {auto['origen']} "
            "(otro mercado) y puede diferir del mismo modelo vendido en Chile. Úsalo como estimación."
        )
        # No se usa para elegir el combustible (no es dato del fabricante), pero sí para advertir.
        if auto.get("premium") == "Sí":
            just.append(
                "⚠ En Canadá este modelo figura con gasolina premium. Confirma en el manual del vehículo "
                "qué octanaje exige antes de cargar 93."
            )
        elif auto.get("premium", "").startswith("Depende"):
            just.append(
                "⚠ En Canadá algunas versiones de este modelo piden gasolina premium. Confirma en el manual "
                "del vehículo qué octanaje exige la tuya."
            )
    if oct_rec is None:
        just.append(
            "Todavía no tenemos verificado el octanaje que recomienda el fabricante de este auto, "
            "así que recomendamos el combustible más barato. Confírmalo en el manual del vehículo."
        )
    elif not aptas:
        just.append(
            f"Ninguna de las estaciones tiene precio de un combustible de {oct_rec} octanos o más, que es lo que recomienda "
            f"el fabricante. Se muestra el más barato disponible: confirma en el manual del vehículo qué puedes cargar."
        )
    elif recomendado is barato:
        just.append(
            f"Es el combustible compatible más barato y cumple el octanaje que recomienda "
            f"el fabricante ({oct_rec})."
        )
    else:
        dif = recomendado["costo_km"] - barato["costo_km"]
        just.append(
            f"El {barato['combustible']} sale ${dec(dif)} por km más barato, pero este auto "
            f"recomienda mínimo {oct_rec} octanos. Con menos octanaje el motor puede corregir "
            f"el encendido para evitar detonación, lo que puede costar eficiencia y desgaste "
            f"a largo plazo. Por eso recomendamos el {recomendado['combustible']}."
        )
    superiores = [o for o in opciones if int(o["combustible"]) > int(recomendado["combustible"])]
    if oct_rec is not None and superiores:
        just.append(
            "Un octanaje mayor al recomendado cuesta más y, en general, no mejora el "
            "rendimiento ni la vida útil de un motor que no lo requiere."
        )

    # Textos para mostrar
    for o in opciones:
        o["costo_km_txt"] = "$" + dec(o["costo_km"])
        o["gasto_txt"] = clp(o["gasto_mes"])
        o["precio_txt"] = clp(o["precio"])
        o["fecha_txt"] = o["fecha"][:16] if o["fecha"] else "sin fecha informada"
        o["es_recomendado"] = o is recomendado

    return {
        "auto": auto["nombre"],
        "referencial": auto.get("referencial", False),
        "origen": auto.get("origen", ""),
        "oct_rec": oct_rec,
        "recomendado": recomendado,
        "opciones": opciones,
        "justificacion": just,
    }


# --- 4. Vista ---
def mostrar_pagina(request):
    contexto = {
        "vehiculos": [a["nombre"] for a in catalogo.values()],
        "marcas": agrupar_por_marca([(a["nombre"],) for a in catalogo.values()]),
        "datos": {},
    }

    if request.method == "POST":
        datos = request.POST.dict()
        contexto["datos"] = datos
        accion = datos.get("accion")

        # Tarjeta izquierda: recomendador
        if accion == "recomendar":
            errores = []
            auto, error_auto = buscar_auto(datos.get("vehiculo", ""))
            if error_auto:
                errores.append(error_auto)
            km_mes = a_numero(datos.get("km_mes", ""))
            if km_mes is None or km_mes <= 0 or km_mes > 30000:
                errores.append("Los km al mes deben ser un número mayor que 0 y de hasta 30000.")

            if errores:
                contexto["errores"] = errores
            else:
                precios = bencina.obtener_datos()
                contexto["precios"] = precios
                contexto["max_dias"] = bencina.MAX_DIAS
                comuna = datos.get("comuna", "").strip()
                lista = bencina.filtrar_estaciones(precios.estaciones, comuna=comuna)
                if not precios.ok:
                    contexto["errores"] = [precios.aviso]
                elif not lista:
                    contexto["errores"] = [f"No hay estaciones en la comuna «{comuna}»."]
                else:
                    resultado = recomendar_combustible(auto, km_mes, lista)
                    if "error" in resultado:
                        contexto["errores"] = [resultado["error"]]
                    else:
                        resultado["ambito"] = comuna or "todo Chile"
                        resultado["n_estaciones"] = len(lista)
                        contexto["resultado"] = resultado

        # Tarjeta derecha: costo de un repostaje
        elif accion == "repostaje":
            litros = a_numero(datos.get("litros", ""))
            precio = a_numero(datos.get("precio_litro", ""))
            errores = []
            if litros is None or litros <= 0 or litros > 500:
                errores.append("Los litros deben ser un número mayor que 0 y de hasta 500.")
            if precio is None or precio <= 0 or precio > 10000:
                errores.append("El precio por litro debe ser un número mayor que 0 y de hasta 10000.")

            if errores:
                contexto["errores_rep"] = errores
            else:
                contexto["repostaje"] = {
                    "total": clp(int((Decimal(str(litros)) * Decimal(str(precio))).quantize(Decimal(1), ROUND_HALF_UP))),  # exacto, sin errores de coma flotante
                    "detalle": f"{num(litros)} L × ${num(precio, 2)}/L" if precio != int(precio) else f"{num(litros)} L × {clp(precio)}/L",
                }

    return render(request, "viajes/inicio.html", contexto)

# --- 5. Datos para el mapa ---
@require_GET
def estaciones_json(request):
    """Estaciones con coordenadas y precios 93/95/97, en el mismo formato que usa el recomendador.

    Filtros opcionales por query string: comuna, region y q (marca, dirección o comuna).
    """
    datos = bencina.obtener_datos()
    if not datos.ok:
        return JsonResponse({"error": datos.aviso, "estaciones": []}, status=503)

    f = {k: request.GET.get(k, "").strip()[:80] for k in ("comuna", "region", "q")}
    filtradas = bencina.filtrar_estaciones(datos.estaciones, comuna=f["comuna"], region=f["region"], texto=f["q"])

    campos = ("id", "marca", "region", "comuna", "direccion", "lat", "lon", "precios")
    orden = bencina.normalizar_texto
    pares = sorted({(e["comuna"], e["region"]) for e in datos.estaciones if e["comuna"]}, key=lambda c: orden(c[0]))
    return JsonResponse({
        "estaciones": [{k: e[k] for k in campos} for e in filtradas],
        "total": len(datos.estaciones),
        "regiones": sorted({e["region"] for e in datos.estaciones if e["region"]}, key=orden),
        "comunas": [{"nombre": c, "region": r} for c, r in pares],
        "fuente": datos.fuente,
        "consultado": datos.consultado.isoformat() if datos.consultado else None,
        "aviso": datos.aviso,
        "descartados": datos.descartados,
        "max_dias": bencina.MAX_DIAS,
    })
