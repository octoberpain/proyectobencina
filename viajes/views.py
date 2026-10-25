import requests
from django.shortcuts import render

# --- 1. Datos (octanaje None = sin verificar; los precios de estaciones son de ejemplo) ---
catalogo = {
    ("suzuki", "swift"): {
        "nombre": "Suzuki Swift 1.2 ISG",
        "rendimiento": 22.8,
        "combustibles": ["93", "95", "97"],
        "octanaje_recomendado": None,
        "fuente": "Consumo Vehicular (1.2 ISG MT)",
    },
    ("kia", "soluto"): {
        "nombre": "Kia Soluto 1.4",
        "rendimiento": 17.5,
        "combustibles": ["93", "95", "97"],
        "octanaje_recomendado": 93,
        "fuente": "Consumo Vehicular (1.4 5MT); octanaje según ficha de Kia Chile",
    },
    ("suzuki", "fronx"): {
        "nombre": "Suzuki Fronx 1.5 GL",
        "rendimiento": 19.2,
        "combustibles": ["93", "95", "97"],
        "octanaje_recomendado": None,
        "fuente": "Suzuki Chile (dato del fabricante, sin confirmar en Consumo Vehicular)",
    },
    ("mazda", "cx5"): {
        "nombre": "Mazda CX-5 2.0",
        "rendimiento": 14.2,
        "combustibles": ["93", "95", "97"],
        "octanaje_recomendado": None,
        "fuente": "Mazda Chile (dato del fabricante, sin confirmar en Consumo Vehicular)",
    },
    ("toyota", "yaris"): {
        "nombre": "Toyota Yaris (dato de prueba)",
        "rendimiento": 15.0,
        "combustibles": ["93", "95", "97"],
        "octanaje_recomendado": 93,
        "fuente": "valor del código original, sin fuente",
    },
}

estaciones = [
    {"nombre": "Estación A", "precios": {"93": 1300, "95": 1350, "97": 1400}},
    {"nombre": "Estación B", "precios": {"93": 1290, "95": 1360, "97": 1395}},
    {"nombre": "Estación C", "precios": {"93": 1310, "95": 1340, "97": 1410}},
]

# API opcional (verificar antes de usar). None = solo datos locales.
# JSON esperado: [{"nombre": "X", "precios": {"93": 1300}}, ...]
API_PRECIOS_URL = None
API_TIMEOUT = 3


# --- 2. Auxiliares ---
def obtener_estaciones():
    """Precios desde la API; si falla, datos locales."""
    if not API_PRECIOS_URL:
        return estaciones, "datos locales de ejemplo"
    try:
        resp = requests.get(API_PRECIOS_URL, timeout=API_TIMEOUT)
        resp.raise_for_status()
        datos = resp.json()
        if (
            not isinstance(datos, list)
            or not datos
            or not all(isinstance(e, dict) and isinstance(e.get("precios"), dict) for e in datos)
        ):
            raise ValueError("Respuesta inválida")
        return datos, "API externa"
    except (requests.RequestException, ValueError):
        return estaciones, "datos locales de ejemplo (la API no respondió)"


def a_numero(texto):
    """Texto a número (acepta coma); None si no es válido."""
    try:
        n = float(str(texto).strip().replace(",", "."))
    except ValueError:
        return None
    if n != n or n in (float("inf"), float("-inf")):
        return None
    return n


def clp(x):
    return "$" + f"{round(x):,}".replace(",", ".")


def dec(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


# --- 3. Recomendación: costo/km = precio ÷ rendimiento; respeta el octanaje del fabricante ---
def recomendar_combustible(clave, km_mes, estaciones):
    if clave not in catalogo:
        return {"error": "Vehículo no encontrado."}

    auto = catalogo[clave]
    opciones = []

    for comb in auto["combustibles"]:
        ofertas = [
            (est["precios"][comb], est.get("nombre", "Sin nombre"))
            for est in estaciones
            if comb in est["precios"]
        ]
        if ofertas:
            precio, estacion = min(ofertas)
            costo_km = precio / auto["rendimiento"]
            opciones.append({
                "combustible": comb,
                "precio": precio,
                "estacion": estacion,
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
        f"(precio de la estación más barata ÷ rendimiento de {dec(auto['rendimiento'])} km/L).",
        f"Fuente del rendimiento: {auto['fuente']}.",
    ]
    if oct_rec is None:
        just.append(
            "Todavía no tenemos verificado el octanaje que recomienda el fabricante de este auto, "
            "así que recomendamos el combustible más barato. Confírmalo en el manual del vehículo."
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
        o["es_recomendado"] = o is recomendado

    return {
        "auto": auto["nombre"],
        "oct_rec": oct_rec,
        "recomendado": recomendado,
        "opciones": opciones,
        "justificacion": just,
    }


# --- 4. Vista ---
def mostrar_pagina(request):
    contexto = {
        "vehiculos": [
            {"clave": f"{m}|{mod}", "nombre": a["nombre"]} for (m, mod), a in catalogo.items()
        ],
        "datos": {},
    }

    if request.method == "POST":
        datos = request.POST.dict()
        contexto["datos"] = datos
        accion = datos.get("accion")

        # Tarjeta izquierda: recomendador
        if accion == "recomendar":
            errores = []
            clave = tuple(datos.get("vehiculo", "").split("|"))
            if clave not in catalogo:
                errores.append("Elige un vehículo de la lista.")
            km_mes = a_numero(datos.get("km_mes", ""))
            if km_mes is None or km_mes <= 0 or km_mes > 30000:
                errores.append("Los km al mes deben ser un número entre 1 y 30000.")

            if errores:
                contexto["errores"] = errores
            else:
                lista, fuente = obtener_estaciones()
                resultado = recomendar_combustible(clave, km_mes, lista)
                if "error" in resultado:
                    contexto["errores"] = [resultado["error"]]
                else:
                    contexto["resultado"] = resultado
                    contexto["fuente"] = fuente

        # Tarjeta derecha: costo de un repostaje
        elif accion == "repostaje":
            litros = a_numero(datos.get("litros", ""))
            precio = a_numero(datos.get("precio_litro", ""))
            errores = []
            if litros is None or litros <= 0 or litros > 500:
                errores.append("Los litros deben ser un número entre 1 y 500.")
            if precio is None or precio <= 0 or precio > 10000:
                errores.append("El precio por litro debe ser un número entre 1 y 10000.")

            if errores:
                contexto["errores_rep"] = errores
            else:
                contexto["repostaje"] = {
                    "total": clp(litros * precio),
                    "detalle": f"{dec(litros, 1).rstrip('0').rstrip(',')} L × {clp(precio)}/L",
                }

    return render(request, "viajes/inicio.html", contexto)