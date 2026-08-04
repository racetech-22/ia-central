from cryptography.fernet import Fernet, MultiFernet
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import TestCase, override_settings

from apps.sala import fields
from apps.sala.models import Proyecto


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
