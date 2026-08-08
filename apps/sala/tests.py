from cryptography.fernet import Fernet, MultiFernet
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import TestCase, override_settings

from apps.sala import fields
from apps.sala.consumers import SalaConsumer
from apps.sala.models import Chat, Proyecto

User = get_user_model()

CHANNEL_LAYERS_EN_MEMORIA = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}


class EncryptedTextFieldTests(TestCase):
    def _crear_proyecto(self, workspace_api_key):
        return Proyecto.objects.create(
            project_key="test-proyecto",
            nombre="Test",
            destino_tipo=Proyecto.DestinoTipo.EXTERNO_SERVIDOR,
            workspace_api_key=workspace_api_key,
        )

    def test_valor_guardado_no_es_texto_plano(self):
        secreto = "sk-ant-workspace-super-secreto"
        proyecto = self._crear_proyecto(secreto)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT workspace_api_key FROM sala_proyecto WHERE id = %s",
                [proyecto.pk],
            )
            valor_crudo = cursor.fetchone()[0]

        self.assertNotEqual(valor_crudo, secreto)
        self.assertNotIn(secreto, valor_crudo)

    def test_roundtrip_devuelve_el_valor_original(self):
        secreto = "sk-ant-workspace-super-secreto"
        proyecto = self._crear_proyecto(secreto)

        releido = Proyecto.objects.get(pk=proyecto.pk)

        self.assertEqual(releido.workspace_api_key, secreto)

    def test_valor_vacio_no_se_cifra(self):
        proyecto = self._crear_proyecto(None)

        releido = Proyecto.objects.get(pk=proyecto.pk)

        self.assertIsNone(releido.workspace_api_key)


class LoadMultiFernetTests(TestCase):
    """Prueba _load_multifernet() directamente, sin depender del singleton
    de módulo (que ya se construyó una sola vez al arrancar con la clave
    real) — así se puede probar el caso de clave faltante/inválida sin
    reiniciar el proceso."""

    @override_settings(CREDENTIALS_ENCRYPTION_KEY=None)
    def test_clave_faltante_falla_claro(self):
        with self.assertRaises(ImproperlyConfigured):
            fields._load_multifernet()

    @override_settings(CREDENTIALS_ENCRYPTION_KEY="esto-no-es-una-clave-fernet-valida")
    def test_clave_invalida_falla_claro(self):
        with self.assertRaises(ImproperlyConfigured):
            fields._load_multifernet()

    def test_clave_valida_construye_multifernet(self):
        clave = Fernet.generate_key().decode()
        with override_settings(CREDENTIALS_ENCRYPTION_KEY=clave):
            mf = fields._load_multifernet()
        self.assertIsInstance(mf, MultiFernet)


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_EN_MEMORIA)
class SalaConsumerTests(TestCase):
    """WebSocket de la sala (ADR-035). Channel layer en memoria — los tests
    no deben depender de Redis. El scope se arma a mano (usuario y
    url_route) en vez de pasar por AuthMiddlewareStack/URLRouter reales,
    mismo patrón que documenta Channels para testear un consumer aislado."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_user(
            username="superuser-sala", password="no-se-usa", is_superuser=True, is_staff=True
        )
        cls.usuario_comun = User.objects.create_user(
            username="usuario-comun-sala", password="no-se-usa"
        )
        cls.proyecto = Proyecto.objects.create(
            project_key="sala-test",
            nombre="Sala test",
            destino_tipo=Proyecto.DestinoTipo.NATIVO,
        )
        cls.chat = Chat.objects.create(
            proyecto=cls.proyecto, consultor_session_id="s-sala-test", titulo="chat de prueba"
        )

    def _communicator(self, chat_id, user):
        comunicador = WebsocketCommunicator(
            SalaConsumer.as_asgi(), f"/ws/sala/{chat_id}/"
        )
        comunicador.scope["user"] = user
        comunicador.scope["url_route"] = {"kwargs": {"chat_id": str(chat_id)}}
        return comunicador

    async def test_rechaza_usuario_no_autenticado(self):
        comunicador = self._communicator(self.chat.id, AnonymousUser())

        connected, codigo_cierre = await comunicador.connect()

        self.assertFalse(connected)
        self.assertEqual(codigo_cierre, 4403)
        await comunicador.disconnect()

    async def test_rechaza_usuario_autenticado_sin_superusuario(self):
        comunicador = self._communicator(self.chat.id, self.usuario_comun)

        connected, codigo_cierre = await comunicador.connect()

        self.assertFalse(connected)
        self.assertEqual(codigo_cierre, 4403)
        await comunicador.disconnect()

    async def test_acepta_superusuario_y_reenvia_evento_de_grupo(self):
        comunicador = self._communicator(self.chat.id, self.superuser)

        connected, _ = await comunicador.connect()
        self.assertTrue(connected)

        primer_mensaje = await comunicador.receive_json_from()
        self.assertEqual(primer_mensaje, {"tipo": "conectado", "chat_id": self.chat.id})

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"chat_{self.chat.id}",
            {"type": "sala.evento", "payload": {"tipo": "prueba", "valor": 42}},
        )

        evento = await comunicador.receive_json_from()
        self.assertEqual(evento, {"tipo": "prueba", "valor": 42})

        await comunicador.disconnect()
