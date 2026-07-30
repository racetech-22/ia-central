from django.contrib import admin
from django.apps import AppConfig


class AdminpanelConfig(AppConfig):
    """App base del panel administrativo (ver ARQUITECTURA.md §4).

    Por ahora solo personaliza el admin integrado de Django. El panel real
    (costos, modelos activos, salud de conectores) se construye en Fase 5.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.adminpanel"
    verbose_name = "Panel administrativo"

    def ready(self):
        admin.site.site_header = "IA CENTRAL"
        admin.site.site_title = "IA CENTRAL"
        admin.site.index_title = "Panel administrativo"
