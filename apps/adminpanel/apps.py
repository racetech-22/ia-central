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
        # Portada con un link a /mapa/ (ver apps/adminpanel/views.py) sin
        # tocar el template real de contrib.admin: adminpanel/index.html
        # extiende admin/index.html y se resuelve sin ambigüedad de orden
        # de INSTALLED_APPS porque su ruta relativa no colisiona con la de
        # ningún otro template instalado.
        admin.site.index_template = "adminpanel/index.html"
