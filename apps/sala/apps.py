from django.apps import AppConfig


class SalaConfig(AppConfig):
    """Modelo de datos de la sala de discusión (ADR-025 punto 7, pilar 1 de ADR-024).

    Solo el modelo de datos por ahora — la migración a ASGI/Channels (ADR-025
    §9.7, ADR-026) y el protocolo de conexión saliente (ADR-025 §9) son
    subtareas siguientes, no implementadas acá.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sala"
    verbose_name = "Sala de discusión"
