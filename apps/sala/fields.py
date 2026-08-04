from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


def _load_multifernet() -> MultiFernet:
    """Construye el MultiFernet desde CREDENTIALS_ENCRYPTION_KEY.

    Se llama a nivel de módulo (ver abajo), así que corre cuando Django
    importa este modelo al arrancar — falla clara al arrancar, no en
    silencio ni recién en el primer save/load.
    """
    raw = getattr(settings, "CREDENTIALS_ENCRYPTION_KEY", None)
    if not raw:
        raise ImproperlyConfigured(
            "CREDENTIALS_ENCRYPTION_KEY no está configurada (ver env.example). "
            "Requerida por apps.sala.fields.EncryptedTextField."
        )
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if not keys:
        raise ImproperlyConfigured(
            "CREDENTIALS_ENCRYPTION_KEY está vacía después de separar por comas."
        )
    try:
        fernets = [Fernet(key.encode()) for key in keys]
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            "CREDENTIALS_ENCRYPTION_KEY contiene una clave Fernet inválida "
            "(debe ser base64 urlsafe de 32 bytes)."
        ) from exc
    return MultiFernet(fernets)


_multifernet = _load_multifernet()


class EncryptedTextField(models.TextField):
    """TextField cifrado con Fernet (ADR-025 punto 8).

    Cifra al guardar, descifra al leer. Usa MultiFernet: la primera clave de
    CREDENTIALS_ENCRYPTION_KEY (separadas por coma) cifra; todas se prueban
    al descifrar, dejando lista la rotación de clave a futuro (agregar una
    clave nueva al principio de la lista sin invalidar lo ya cifrado con las
    anteriores).
    """

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return _multifernet.encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        return _multifernet.decrypt(value.encode()).decode()
