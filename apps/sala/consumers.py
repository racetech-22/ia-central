import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Chat


class SalaConsumer(AsyncWebsocketConsumer):
    """WebSocket de la sala (ADR-035): un grupo por chat (``chat_<id>``), de
    empuje. El servidor manda cosas al navegador vía ``sala_evento`` (el
    único handler de grupo); el navegador no manda nada que mute estado —
    solo responde a ``ping`` — las decisiones de permiso viajan por HTTP,
    ver ADR-035 punto 3.
    """

    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated or not user.is_superuser:
            await self.close(code=4403)
            return

        self.chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
        existe = await self._chat_existe(self.chat_id)
        if not existe:
            await self.close(code=4404)
            return

        self.group_name = f"chat_{self.chat_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(
            text_data=json.dumps({"tipo": "conectado", "chat_id": int(self.chat_id)})
        )

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data) if text_data else {}
        except (TypeError, ValueError):
            data = {}

        if data.get("tipo") == "ping":
            await self.send(text_data=json.dumps({"tipo": "pong"}))
        else:
            await self.send(
                text_data=json.dumps({"tipo": "error", "detalle": "mensaje no reconocido"})
            )

    async def sala_evento(self, event):
        """Handler de grupo (``group_send(..., {"type": "sala.evento", ...})``)
        — reenvía ``event["payload"]`` tal cual al socket."""
        await self.send(text_data=json.dumps(event["payload"]))

    @database_sync_to_async
    def _chat_existe(self, chat_id):
        return Chat.objects.filter(pk=chat_id).exists()
