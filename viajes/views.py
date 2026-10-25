import requests
from django.shortcuts import render

# --- Datos estáticos ---
catalogo = {
    ("toyota", "yaris"): {
        "rendimiento": 15.0,
        "combustibles": ["93", "95", "97"]
    }
}

estaciones = [
    {
        "nombre": "Estación A",
        "precios": {"93": 1300, "95": 1350, "97": 1400}
    }
]

FACTOR_CAMINO = {
    "ciudad": 0.85,
    "carretera": 1.00,
    "montaña": 0.90
}

# API opcional: poner aquí una URL que HAYA verificado. Si es None, se usan solo datos locales.
# Formato JSON esperado: [{"nombre": "X", "precios": {"93": 1300, "95": 1350}}, ...]
API_PRECIOS_URL = None
API_TIMEOUT = 3  # segundos


def obtener_estaciones():
    """Intenta leer precios desde la API; si falla, devuelve los datos estáticos."""
    if not API_PRECIOS_URL:
        return estaciones, "datos locales"
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
        return estaciones, "datos locales (la API no respondió)"


def factor_altitud(altitud):
    if altitud < 1000:
        return 1.00
    elif altitud < 2500:
        return 0.95
    else:
        return 0.90


def recomendar_combustible(marca, modelo, altitud, tipo_camino, estaciones):
    clave = (marca.lower(), modelo.lower())

    if clave not in catalogo:
        return {"error": "Vehículo no encontrado."}

    opciones = []

    for comb in catalogo[clave]["combustibles"]:
        mejor_precio = min(
            [
                est["precios"].get(comb, float("inf"))
                for est in estaciones
                if comb in est["precios"]
            ],
            default=None
        )

        if mejor_precio is not None:
            rend = (
                catalogo[clave]["rendimiento"]
                * FACTOR_CAMINO.get(tipo_camino, 1)
                * factor_altitud(altitud)
            )

            opciones.append({
                "combustible": comb,
                "costo_km": mejor_precio / rend
            })

    if not opciones:
        return {"error": "No hay precios."}

    opciones.sort(key=lambda o: o["costo_km"])

    return {
        "recomendado": opciones[0],
        "opciones": opciones
    }


def mostrar_pagina(request):
    contexto = {"caminos": list(FACTOR_CAMINO), "datos": {}}

    if request.method == "POST":
        marca = request.POST.get("marca", "").strip()
        modelo = request.POST.get("modelo", "").strip()
        altitud_txt = request.POST.get("altitud", "").strip().replace(",", ".")
        tipo_camino = request.POST.get("tipo_camino", "").strip()
        contexto["datos"] = {
            "marca": marca, "modelo": modelo,
            "altitud": altitud_txt, "tipo_camino": tipo_camino,
        }

        errores = []
        if not marca:
            errores.append("Ingresa la marca.")
        if not modelo:
            errores.append("Ingresa el modelo.")
        if tipo_camino not in FACTOR_CAMINO:
            errores.append("Elige un tipo de camino válido.")
        altitud = None
        try:
            altitud = float(altitud_txt)
            if altitud != altitud or altitud in (float("inf"), float("-inf")):
                raise ValueError
            if altitud < 0 or altitud > 6000:
                errores.append("La altitud debe estar entre 0 y 6000 m.")
        except ValueError:
            errores.append("La altitud debe ser un número (ej: 520).")

        if errores:
            contexto["errores"] = errores
        else:
            lista, fuente = obtener_estaciones()
            resultado = recomendar_combustible(marca, modelo, altitud, tipo_camino, lista)
            if "error" in resultado:
                contexto["errores"] = [resultado["error"]]
            else:
                contexto["resultado"] = resultado
                contexto["fuente"] = fuente

    return render(request, "viajes/inicio.html", contexto)