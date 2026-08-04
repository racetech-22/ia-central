from django.conf import settings
from django.db import models

from .fields import EncryptedTextField


class Proyecto(models.Model):
    """Destino registrado en la sala — nativo o externo (ADR-025 punto 7)."""

    class DestinoTipo(models.TextChoices):
        NATIVO = "nativo", "Nativo"
        EXTERNO_SERVIDOR = "externo_servidor", "Externo (servidor)"
        EXTERNO_PC_LOCAL = "externo_pc_local", "Externo (PC local)"

    project_key = models.SlugField(max_length=200, unique=True)
    nombre = models.CharField(max_length=200)
    destino_tipo = models.CharField(max_length=20, choices=DestinoTipo.choices)
    dominio = models.CharField(max_length=255, blank=True)
    # Opcional: el destino nativo no la necesita (ADR-025 punto 6/7).
    workspace_api_key = EncryptedTextField(blank=True, null=True)
    connection_token_hash = models.CharField(
        max_length=64, unique=True, blank=True, null=True
    )
    token_generado_en = models.DateTimeField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Chat(models.Model):
    """Conversación independiente contra un Proyecto — puede haber varias."""

    proyecto = models.ForeignKey(
        Proyecto, related_name="chats", on_delete=models.CASCADE
    )
    session_id = models.CharField(max_length=255)
    titulo = models.CharField(max_length=255, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return self.titulo or self.session_id


class EntradaSesion(models.Model):
    """Tabla espejo del ``SessionStore`` del SDK (ADR-025 punto 7).

    Campos calcados del ``Protocol`` real (``SessionKey``/``SessionStoreEntry``
    de ``claude-agent-sdk``, tag ``v0.2.128``): no es un esquema de "Mensaje"
    inventado, el blob de ``entry`` se persiste tal cual, sin interpretarlo.
    """

    project_key = models.CharField(max_length=255)
    session_id = models.CharField(max_length=255)
    # Vacío para el planificador; "subagents/agent-{id}" para el ejecutor
    # sub-agente (ver SessionKey.subpath).
    subpath = models.CharField(max_length=255, blank=True)
    uuid = models.CharField(max_length=64, blank=True, null=True)
    entry = models.JSONField()
    mtime = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["mtime"]
        indexes = [
            models.Index(fields=["project_key", "session_id", "subpath"]),
        ]

    def __str__(self):
        return f"{self.project_key}/{self.session_id}"


class SolicitudPermiso(models.Model):
    """Puente de ``can_use_tool`` (ADR-025 punto 1) — no viene del SDK."""

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        APROBADO = "aprobado", "Aprobado"
        DENEGADO = "denegado", "Denegado"
        CADUCADO = "caducado", "Caducado"

    chat = models.ForeignKey(
        Chat, related_name="solicitudes_permiso", on_delete=models.CASCADE
    )
    request_id = models.CharField(max_length=64, unique=True)
    tool_name = models.CharField(max_length=255)
    tool_input = models.JSONField()
    # Nombres calcados de ToolPermissionContext (SDK), no traducidos.
    title = models.TextField(blank=True)
    display_name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    agent_id = models.CharField(max_length=255, blank=True, null=True)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.PENDIENTE
    )
    decidido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL
    )
    decidido_en = models.DateTimeField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.tool_name} ({self.estado})"
