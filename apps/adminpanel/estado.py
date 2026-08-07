"""Carga y validación de docs/estado.yml (ADR-029), fuente estructurada del
mapa de ruta. Módulo compartido: lo usa la vista de /mapa/, el management
command validar_estado (invocado por .githooks/pre-commit) y los tests —
una sola implementación de la validación, no una copia en bash y otra en
Python.
"""

from pathlib import Path

import yaml
from django.conf import settings

ESTADOS_VALIDOS = {"construido", "disenado", "pendiente"}

# Las etiquetas con acentos viven acá, no en el dato (ADR-029 decisión 2).
ETIQUETAS_ESTADO = {
    "construido": "construido",
    "disenado": "diseñado, sin código",
    "pendiente": "pendiente",
}
# Extensión solo para el estado agregado de un pilar con subtareas mixtas
# (ni todo construido, ni todo pendiente, ni todo disenado) — nunca es el
# valor "estado" de una pieza individual, así que no vive en ESTADOS_VALIDOS.
ETIQUETA_PILAR_MIXTO = "en progreso"

RUTA_ESTADO = Path(settings.BASE_DIR) / "docs" / "estado.yml"
RUTA_ADRS = Path(settings.BASE_DIR) / "docs" / "decisiones"


def cargar_estado(ruta=None):
    ruta = Path(ruta) if ruta else RUTA_ESTADO
    with open(ruta, encoding="utf-8") as f:
        datos = yaml.safe_load(f)
    return datos or {}


def _adr_existe(adr_id, raiz_adrs):
    return any(raiz_adrs.glob(f"{adr_id}-*.md"))


def validar_estado(datos, raiz_repo=None):
    """Devuelve una lista de errores en texto plano; vacía si el archivo es válido."""
    raiz_repo = Path(raiz_repo) if raiz_repo else Path(settings.BASE_DIR)
    raiz_adrs = raiz_repo / "docs" / "decisiones"
    errores = []

    piezas = datos.get("piezas")
    if not isinstance(piezas, list) or not piezas:
        errores.append("falta la sección 'piezas', o está vacía")
        piezas = []

    campos_requeridos_pieza = ("id", "nombre", "estado", "pilar", "fase", "adrs")
    ids_vistos = set()
    for pieza in piezas:
        pid = pieza.get("id", "<sin id>")
        for campo in campos_requeridos_pieza:
            if campo not in pieza:
                errores.append(f"pieza '{pid}': falta el campo '{campo}'")
        if pid in ids_vistos:
            errores.append(f"pieza '{pid}': id duplicado")
        ids_vistos.add(pid)

        estado = pieza.get("estado")
        if estado not in ESTADOS_VALIDOS:
            errores.append(
                f"pieza '{pid}': estado '{estado}' inválido "
                f"(debe ser uno de {sorted(ESTADOS_VALIDOS)})"
            )

        for adr in pieza.get("adrs") or []:
            if not _adr_existe(adr, raiz_adrs):
                errores.append(
                    f"pieza '{pid}': ADR '{adr}' no existe como archivo real en docs/decisiones/"
                )

        if estado == "construido":
            artefactos = pieza.get("artefactos") or []
            if not artefactos:
                errores.append(f"pieza '{pid}': estado 'construido' sin 'artefactos' declarados")
            for artefacto in artefactos:
                if not (raiz_repo / artefacto).exists():
                    errores.append(
                        f"pieza '{pid}': artefacto '{artefacto}' no existe en el repo"
                    )

    decisiones = datos.get("decisiones_abiertas")
    if decisiones is None:
        errores.append("falta la sección 'decisiones_abiertas'")
        decisiones = []

    campos_requeridos_decision = ("id", "texto", "adr", "depende_de")
    for decision in decisiones:
        did = decision.get("id", "<sin id>")
        for campo in campos_requeridos_decision:
            if campo not in decision:
                errores.append(f"decisión abierta '{did}': falta el campo '{campo}'")
        adr = decision.get("adr")
        if adr and not _adr_existe(adr, raiz_adrs):
            errores.append(
                f"decisión abierta '{did}': ADR '{adr}' no existe como archivo real en docs/decisiones/"
            )

    return errores
