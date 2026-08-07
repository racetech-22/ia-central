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
    """Conversación independiente contra un Proyecto — puede haber varias.

    Historiales de Consultor y Ejecutor separados, correlacionados por este
    Chat, no por un identificador común (ADR-033 punto 1): el Consultor
    conversa en una sola sesión continua (``consultor_session_id``), pero
    el Ejecutor abre una sesión nueva por cada reciclado de su contenedor
    (ADR-030) — ver ``SesionEjecutor``.
    """

    proyecto = models.ForeignKey(
        Proyecto, related_name="chats", on_delete=models.CASCADE
    )
    # Antes "session_id" a secas — ambiguo desde que hay dos roles (ADR-033
    # punto 2). Es la sesión del Consultor, que sigue siendo una sola por
    # Chat (corre sobre el Claude Agent SDK vía orchestrator.run(...)).
    consultor_session_id = models.CharField(max_length=255)
    titulo = models.CharField(max_length=255, blank=True)
    # Elección de agente+modelo del catálogo de ADR-027, por chat y no por
    # proyecto (ADR-030 punto 1).
    agente = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    # Rama propia del chat donde el Ejecutor commitea en puntos de control
    # (ADR-030 punto 6) — la durabilidad del trabajo depende de esto, no del
    # contenedor, que se recicla.
    rama = models.CharField(max_length=255, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return self.titulo or self.consultor_session_id


class SesionEjecutor(models.Model):
    """Tabla de asignaciones que ADR-030 punto 5 y ADR-031 punto 5 daban por
    existente sin definirla (ADR-033 punto 3) — asignar un Ejecutor a un
    chat y abrir una sesión de Ejecutor son el mismo hecho, no dos tablas.

    Cada fila hace además de ``session_epoch`` de ADR-025 §9.4 (ADR-033
    punto 4): al reciclarse el contenedor del Ejecutor se cierra la fila y
    se abre otra, y toda solicitud de permiso pendiente que apunte a la fila
    vieja caduca por construcción — no hace falta un campo de epoch aparte.
    """

    class Estado(models.TextChoices):
        EN_COLA = "en_cola", "En cola"
        ACTIVA = "activa", "Activa"
        TERMINADA = "terminada", "Terminada"
        CADUCADA = "caducada", "Caducada"

    chat = models.ForeignKey(
        Chat, related_name="sesiones_ejecutor", on_delete=models.CASCADE
    )
    # Vacío mientras está en cola: todavía no hay sesión ACP abierta.
    acp_session_id = models.CharField(max_length=255, blank=True)
    # Cuál de los N Ejecutores de población fija (ADR-030 punto 2) tiene
    # asignado; nulo mientras espera turno.
    slot = models.PositiveIntegerField(null=True, blank=True)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.EN_COLA
    )
    iniciada_en = models.DateTimeField(null=True, blank=True)
    terminada_en = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        constraints = [
            # A lo sumo una sesión activa por slot: dos chats no pueden
            # creer que tienen el mismo Ejecutor a la vez.
            models.UniqueConstraint(
                fields=["slot"],
                condition=models.Q(estado="activa"),
                name="un_solo_ejecutor_activo_por_slot",
            ),
            # A lo sumo una sesión activa por chat (ADR-030 punto 1: un
            # Ejecutor por chat, no por proyecto).
            models.UniqueConstraint(
                fields=["chat"],
                condition=models.Q(estado="activa"),
                name="un_solo_ejecutor_activo_por_chat",
            ),
        ]

    def __str__(self):
        return f"{self.chat_id} · slot {self.slot} ({self.estado})"


class EntradaSesion(models.Model):
    """Tabla espejo del ``SessionStore`` del SDK (ADR-025 punto 7) — historial
    del Consultor únicamente, que sigue corriendo sobre el Claude Agent SDK
    vía ``orchestrator.run(...)`` (ADR-012). El Ejecutor salió del SDK con la
    enmienda 2026-08-06 a ADR-025 y ya no aloja acá su historial (ADR-033
    punto 5) — su propio historial queda fuera de alcance de ADR-033.

    Campos calcados del ``Protocol`` real (``SessionKey``/``SessionStoreEntry``
    de ``claude-agent-sdk``, tag ``v0.2.128``): no es un esquema de "Mensaje"
    inventado, el blob de ``entry`` se persiste tal cual, sin interpretarlo.
    """

    project_key = models.CharField(max_length=255)
    session_id = models.CharField(max_length=255)
    # Vacío para el Consultor en el caso normal (ver SessionKey.subpath). Ya
    # no se usa "subagents/agent-{id}" para alojar al Ejecutor como
    # sub-agente — ese modelo se dio de baja en la enmienda 2026-08-06 a
    # ADR-025 (ADR-033).
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
    """Puente de ``can_use_tool`` (ADR-025 punto 1) — no viene del SDK.

    Sin tocar por ADR-033 a propósito: sus campos (``title``/``display_name``/
    ``description``/``agent_id``) vienen de ``ToolPermissionContext`` del SDK,
    que la enmienda 2026-08-06 a ADR-025 da de baja para ACP v1. El rediseño
    sobre los campos reales de ``session/request_permission`` v1 es la
    decisión abierta ``esquema_solicitud_permiso_v1``, todavía sin resolver
    — se deja marcado en vez de tocarlo a medias.
    """

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
