from django.shortcuts import render

def mostrar_pagina(request):
    return render(request, 'viajes/inicio.html')
# Create your views here.
