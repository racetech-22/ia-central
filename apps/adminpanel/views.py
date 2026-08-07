from collections import defaultdict

from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render

from apps.adminpanel.estado import ETIQUETA_PILAR_MIXTO, ETIQUETAS_ESTADO, cargar_estado

# Nombre y resumen de cada uno de los cinco pilares de ADR-024 — taxonomía
# fija que solo cambia si se enmienda esa ADR, a diferencia del estado de
# cada pieza (eso sí viene de docs/estado.yml, ver ADR-029).
PILARES = {
    1: (
        "Sala de discusión y memoria básica",
        "Consultor, Ejecutor y Fernando conversando, con memoria básica de conversación desde el arranque.",
    ),
    2: (
        "Motor de confianza / permisos unificado",
        "Cuando haga falta ir más allá del modelo de permisos actual de Claude Code.",
    ),
    3: (
        "Memoria profunda, RAG",
        "Crece en paralelo desde el pilar 1, sin bloquear nada.",
    ),
    4: (
        "Panel administrativo",
        "Fase 5, naciendo pantalla por pantalla según haga falta.",
    ),
    5: (
        "Multi-modelo con debate",
        "Fase 4, la pieza más compleja, deliberadamente al final.",
    ),
}


def _con_etiqueta(pieza):
    return {**pieza, "etiqueta": ETIQUETAS_ESTADO[pieza["estado"]]}


def _estado_agregado(piezas_pilar):
    estados = {p["estado"] for p in piezas_pilar}
    if len(estados) == 1:
        return estados.pop()
    return "mixto"


@user_passes_test(lambda u: u.is_superuser, login_url="admin:login")
def mapa(request):
    """Hoja de ruta de IA CENTRAL: derivada de docs/estado.yml (ADR-029), sin
    consultas a la base ni JavaScript."""
    datos = cargar_estado()
    piezas = datos.get("piezas", [])

    base = [_con_etiqueta(p) for p in piezas if p.get("pilar") == "base"]

    por_pilar = defaultdict(list)
    for p in piezas:
        if isinstance(p.get("pilar"), int):
            por_pilar[p["pilar"]].append(p)

    pilares = []
    for numero, (nombre, resumen) in sorted(PILARES.items()):
        piezas_pilar = por_pilar.get(numero, [])
        estado = _estado_agregado(piezas_pilar) if piezas_pilar else "pendiente"
        pilares.append(
            {
                "numero": numero,
                "nombre": nombre,
                "resumen": resumen,
                "estado": estado,
                "etiqueta": ETIQUETA_PILAR_MIXTO if estado == "mixto" else ETIQUETAS_ESTADO[estado],
                "fase": piezas_pilar[0].get("fase") if len(piezas_pilar) == 1 else None,
                "subtareas": [_con_etiqueta(p) for p in piezas_pilar] if len(piezas_pilar) > 1 else [],
            }
        )

    contexto = {
        "base": base,
        "pilares": pilares,
        "decisiones_abiertas": datos.get("decisiones_abiertas", []),
    }
    return render(request, "adminpanel/mapa.html", contexto)
