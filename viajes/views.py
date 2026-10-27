import unicodedata

from django.shortcuts import render

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
    normalizar(n): {"nombre": n, "rendimiento": r, "octanaje_recomendado": o, "fuente": f}
    for n, r, o, f in AUTOS
}


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
    if coincidencias:
        nombres = ", ".join(catalogo[k]["nombre"] for k in coincidencias[:5])
        return None, f"Hay varios parecidos: {nombres}. Elige uno de la lista."
    return None, "No encontramos ese vehículo en el catálogo."


def clp(x):
    return "$" + f"{round(x):,}".replace(",", ".")


def dec(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


# --- 3. Recomendación: costo/km = precio ÷ rendimiento; respeta el octanaje del fabricante ---
def recomendar_combustible(auto, km_mes, estaciones):
    """estaciones: lista en el formato de bencina.py (precios por combustible con fecha)."""
    opciones = []

    for comb in COMBUSTIBLES:
        ofertas = [(est["precios"][comb]["precio"], est["id"], est) for est in estaciones if comb in est["precios"]]
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
        o["fecha_txt"] = o["fecha"][:16] if o["fecha"] else "sin fecha informada"
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
    contexto = {"vehiculos": [a["nombre"] for a in catalogo.values()], "datos": {}}

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
                errores.append("Los km al mes deben ser un número entre 1 y 30000.")

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