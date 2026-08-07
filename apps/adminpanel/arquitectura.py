"""Verificación de que ARQUITECTURA.md §6 (Registro de decisiones) coincida
con los archivos ADR reales de docs/decisiones/, en los dos sentidos. Ver
ADR-032. Mismo patrón que apps/adminpanel/estado.py: módulo compartido entre
el management command validar_arquitectura (invocado por
.githooks/pre-commit) y los tests — una sola implementación, no una copia en
bash y otra en Python.
"""

import re
from pathlib import Path

from django.conf import settings

from apps.adminpanel.estado import RUTA_ADRS

RUTA_ARQUITECTURA = Path(settings.BASE_DIR) / "ARQUITECTURA.md"

_RE_ARCHIVO_ADR = re.compile(r"^ADR-(\d{3})-")
_RE_LINEA_SECCION_6 = re.compile(r"^- ADR-(\d{3}):")


def _adrs_reales(raiz_adrs):
    numeros = set()
    for path in raiz_adrs.glob("ADR-*.md"):
        m = _RE_ARCHIVO_ADR.match(path.name)
        if m:
            numeros.add(m.group(1))
    return numeros


def extraer_seccion_6(contenido):
    """Devuelve el texto entre '## 6. Registro de decisiones' y el siguiente
    encabezado de nivel '## ' (o el fin del archivo). Cadena vacía si ese
    encabezado no aparece."""
    lineas = contenido.splitlines()
    inicio = None
    for i, linea in enumerate(lineas):
        if linea.strip() == "## 6. Registro de decisiones":
            inicio = i + 1
            break
    if inicio is None:
        return ""

    fin = len(lineas)
    for i in range(inicio, len(lineas)):
        if lineas[i].startswith("## "):
            fin = i
            break

    return "\n".join(lineas[inicio:fin])


def _adrs_en_seccion_6(seccion):
    numeros = set()
    for linea in seccion.splitlines():
        m = _RE_LINEA_SECCION_6.match(linea)
        if m:
            numeros.add(m.group(1))
    return numeros


def validar_arquitectura(contenido_arquitectura, raiz_adrs=None):
    """Devuelve una lista de errores en texto plano; vacía si §6 coincide con
    los archivos ADR reales en los dos sentidos."""
    raiz_adrs = Path(raiz_adrs) if raiz_adrs else RUTA_ADRS
    errores = []

    reales = _adrs_reales(raiz_adrs)
    seccion = extraer_seccion_6(contenido_arquitectura)
    if not seccion:
        errores.append(
            "no se encontró la sección '## 6. Registro de decisiones' en ARQUITECTURA.md"
        )
        return errores

    en_seccion_6 = _adrs_en_seccion_6(seccion)

    faltantes_en_seccion_6 = sorted(reales - en_seccion_6)
    huerfanos_en_seccion_6 = sorted(en_seccion_6 - reales)

    for numero in faltantes_en_seccion_6:
        errores.append(
            f"ADR-{numero}: existe como archivo real, sin renglón '- ADR-{numero}:' en ARQUITECTURA.md §6"
        )

    for numero in huerfanos_en_seccion_6:
        errores.append(
            f"ARQUITECTURA.md §6: renglón 'ADR-{numero}:' sin archivo real correspondiente en docs/decisiones/"
        )

    return errores
