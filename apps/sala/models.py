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
    # Vacío al crear el chat (ADR-035, enmienda 2026-08-08): un chat nace en
    # la Sala antes de que exista sesión de Consultor, se llena cuando el
    # Consultor arranque, no antes.
    consultor_session_id = models.CharField(max_length=255, blank=True)
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


class ActualizacionSesion(models.Model):
    """Log append-only de las notificaciones ``session/update`` del Ejecutor
    (ADR-034 punto 1). Mismo criterio que ADR-025 punto 7 aplicó a
    ``EntradaSesion`` para el Consultor: se persiste el ``payload`` tal cual,
    sin inventarle un esquema de "Mensaje" a algo que el protocolo ya define.

    ``tipo`` (el discriminador ``sessionUpdate``: ``tool_call``,
    ``tool_call_update``, ``agent_message_chunk``, ``plan``,
    ``usage_update``, etc.) es texto libre a propósito, no un
    ``TextChoices`` — la especificación puede sumar tipos nuevos, y un tipo
    no contemplado hoy no debe romper la ingesta.
    """

    sesion = models.ForeignKey(
        SesionEjecutor, related_name="actualizaciones", on_delete=models.CASCADE
    )
    tipo = models.CharField(max_length=50)
    payload = models.JSONField()
    recibido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["recibido_en"]
        indexes = [
            models.Index(fields=["sesion", "recibido_en"]),
        ]

    def __str__(self):
        return f"{self.sesion_id}/{self.tipo}"


class LlamadaHerramienta(models.Model):
    """Proyección mutable de los tool calls del Ejecutor (ADR-034 punto 2).

    Existe además de ``ActualizacionSesion`` por dos motivos verificados
    contra ``https://agentclientprotocol.com/protocol/v1/tool-calls.md``:
    los tool calls son mutables (``pending`` -> ``in_progress`` ->
    ``completed``/``failed``, y "todos los campos salvo ``toolCallId`` son
    opcionales en las actualizaciones"), y ``session/request_permission``
    no trae los detalles de la operación, solo el ``toolCallId`` — sin esta
    proyección no hay con qué mostrarle al Director qué está autorizando.
    """

    class Estado(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    sesion = models.ForeignKey(
        SesionEjecutor, related_name="llamadas", on_delete=models.CASCADE
    )
    tool_call_id = models.CharField(max_length=255)
    title = models.TextField(blank=True)
    # read/edit/delete/move/search/execute/think/fetch/other.
    kind = models.CharField(max_length=20, blank=True)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.PENDING
    )
    raw_input = models.JSONField(null=True, blank=True)
    raw_output = models.JSONField(null=True, blank=True)
    content = models.JSONField(null=True, blank=True)
    locations = models.JSONField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["creado_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["sesion", "tool_call_id"],
                name="tool_call_unico_por_sesion",
            ),
        ]

    def __str__(self):
        return f"{self.tool_call_id} ({self.estado})"


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
    """Puente de ``session/request_permission`` (ADR-034 punto 3) —
    reescrita sobre ACP v1, no sobre ``ToolPermissionContext`` del SDK.

    ACP no devuelve aprobado/denegado: devuelve la elección de una opción
    (verbatim, ``https://agentclientprotocol.com/protocol/v1/tool-calls.md``:
    ``{"outcome": {"outcome": "selected", "optionId": "allow-once"}}``), o
    ``cancelled``. Por eso se guardan las ``opciones`` que ofreció el agente
    tal como llegaron y la ``opcion_elegida``, en vez de un booleano.

    ``cancelada`` y ``caducada`` son causas distintas, no sinónimos: el
    protocolo obliga a responder ``cancelled`` a todo permiso pendiente al
    cancelar un turno (verbatim: *"The Client MUST respond to all pending
    session/request_permission requests with the cancelled outcome"*), lo
    que no es lo mismo que un timeout (ADR-025 §9.4) o el reciclado del
    Ejecutor (ADR-030). ``motivo_cierre`` existe para que el Director vea
    la causa real en vez de encontrarse con una solicitud zombi.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        RESPONDIDA = "respondida", "Respondida"
        CADUCADA = "caducada", "Caducada"
        CANCELADA = "cancelada", "Cancelada"

    # Sobre la llamada concreta que se autoriza, no sobre el Chat — el
    # detalle de la operación (title/kind/content) vive en LlamadaHerramienta,
    # porque session/request_permission solo trae el toolCallId.
    llamada = models.ForeignKey(
        LlamadaHerramienta, related_name="solicitudes", on_delete=models.CASCADE
    )
    request_id = models.CharField(max_length=64, unique=True)
    # Lista de PermissionOption (optionId/name/kind) tal como la ofreció el
    # agente, guardada sin reinterpretar.
    opciones = models.JSONField()
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.PENDIENTE
    )
    opcion_elegida = models.CharField(max_length=255, blank=True)
    motivo_cierre = models.TextField(blank=True)
    decidido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL
    )
    decidido_en = models.DateTimeField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.request_id} ({self.estado})"
