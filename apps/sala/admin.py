from django.contrib import admin

from .models import Chat, EntradaSesion, Proyecto, SolicitudPermiso


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    # workspace_api_key nunca en list_display: no debe aparecer en claro
    # en la lista, aunque el formulario de edición sí la muestre/permita
    # editarla (acceso ya acotado a superusuarios).
    list_display = ("nombre", "project_key", "destino_tipo", "activo", "creado_en")
    list_filter = ("destino_tipo", "activo")
    search_fields = ("nombre", "project_key", "dominio")


class ReadOnlyModelAdmin(admin.ModelAdmin):
    """Solo lectura: sin alta, edición ni borrado desde el admin."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Chat)
class ChatAdmin(ReadOnlyModelAdmin):
    list_display = ("titulo", "session_id", "proyecto", "creado_en")
    list_filter = ("proyecto",)
    search_fields = ("titulo", "session_id")


@admin.register(EntradaSesion)
class EntradaSesionAdmin(ReadOnlyModelAdmin):
    list_display = ("project_key", "session_id", "subpath", "uuid", "mtime")
    list_filter = ("project_key",)
    search_fields = ("project_key", "session_id", "uuid")


@admin.register(SolicitudPermiso)
class SolicitudPermisoAdmin(ReadOnlyModelAdmin):
    list_display = ("tool_name", "chat", "estado", "decidido_por", "creado_en")
    list_filter = ("estado", "tool_name")
    search_fields = ("tool_name", "request_id")
