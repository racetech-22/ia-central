import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.adminpanel.arquitectura import RUTA_ARQUITECTURA, validar_arquitectura
from apps.adminpanel.estado import cargar_estado, validar_estado

User = get_user_model()


class MapaViewTests(TestCase):
    """Verificación end-to-end de /mapa/ (ADR-029): mismo criterio de
    ADR-021/022/023, contra el Client de pruebas real, no llamando a la
    función de vista suelta."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_user(
            username="superuser-mapa", password="no-se-usa", is_superuser=True, is_staff=True
        )
        cls.usuario_comun = User.objects.create_user(
            username="usuario-comun-mapa", password="no-se-usa"
        )

    def test_superuser_ve_el_mapa(self):
        self.client.force_login(self.superuser)
        resp = self.client.get(reverse("mapa"))

        self.assertEqual(resp.status_code, 200)
        cuerpo = resp.content.decode()
        # Una pieza "construido", una "disenado" (con su etiqueta acentuada
        # puesta por el renderizador) y una decisión abierta, para confirmar
        # que la plantilla realmente está leyendo docs/estado.yml y no
        # mostrando una página vacía.
        self.assertIn("MCP server", cuerpo)
        self.assertIn("diseñado, sin código", cuerpo)
        self.assertIn("Decisiones abiertas", cuerpo)

    def test_anonimo_redirige(self):
        resp = self.client.get(reverse("mapa"))
        self.assertEqual(resp.status_code, 302)

    def test_usuario_sin_permiso_redirige(self):
        self.client.force_login(self.usuario_comun)
        resp = self.client.get(reverse("mapa"))
        self.assertEqual(resp.status_code, 302)


class EstadoValidacionTests(TestCase):
    """apps/adminpanel/estado.py es la misma validación que corre
    .githooks/pre-commit (vía manage.py validar_estado) — probada acá
    directamente, sin pasar por el hook, más rápido y sin depender de git."""

    def test_estado_yml_real_es_valido(self):
        """Cubre además el caso inverso que el hook no puede ver barato
        (ver ADR-029, aclaración 1): si alguien borra o mueve un archivo que
        una pieza 'construido' declara como artefacto sin tocar
        docs/estado.yml, este test (que corre siempre, no solo cuando el
        archivo cambia) lo detecta igual."""
        datos = cargar_estado()
        errores = validar_estado(datos)
        self.assertEqual(errores, [], f"docs/estado.yml real no es válido: {errores}")

    def _datos_minimos(self, **overrides):
        base = {
            "piezas": [
                {
                    "id": "pieza_de_prueba",
                    "nombre": "Pieza de prueba",
                    "estado": "pendiente",
                    "pilar": "base",
                    "fase": 2,
                    "adrs": ["ADR-002"],
                }
            ],
            "decisiones_abiertas": [],
        }
        base.update(overrides)
        return base

    def test_detecta_adr_inexistente(self):
        datos = self._datos_minimos()
        datos["piezas"][0]["adrs"] = ["ADR-999"]

        errores = validar_estado(datos)

        self.assertTrue(any("ADR-999" in e for e in errores))

    def test_detecta_estado_invalido(self):
        datos = self._datos_minimos()
        datos["piezas"][0]["estado"] = "construida"  # con acento/género, no ASCII válido

        errores = validar_estado(datos)

        self.assertTrue(any("estado" in e and "inválido" in e for e in errores))

    def test_detecta_artefacto_inexistente_en_pieza_construida(self):
        datos = self._datos_minimos()
        datos["piezas"][0]["estado"] = "construido"
        datos["piezas"][0]["artefactos"] = ["este/archivo/no/existe.py"]

        errores = validar_estado(datos)

        self.assertTrue(any("este/archivo/no/existe.py" in e for e in errores))

    def test_pieza_construida_sin_artefactos_declarados_falla(self):
        datos = self._datos_minimos()
        datos["piezas"][0]["estado"] = "construido"

        errores = validar_estado(datos)

        self.assertTrue(any("sin 'artefactos' declarados" in e for e in errores))

    def test_pieza_construida_con_artefacto_real_pasa(self):
        datos = self._datos_minimos()
        datos["piezas"][0]["estado"] = "construido"
        datos["piezas"][0]["artefactos"] = ["docker-compose.yml"]

        errores = validar_estado(datos)

        self.assertEqual(errores, [])

    def test_decision_abierta_con_adr_inexistente_falla(self):
        datos = self._datos_minimos(
            decisiones_abiertas=[
                {
                    "id": "decision_de_prueba",
                    "texto": "texto",
                    "adr": "ADR-999",
                    "depende_de": "nadie",
                }
            ]
        )

        errores = validar_estado(datos)

        self.assertTrue(any("ADR-999" in e for e in errores))

    def test_cargar_estado_desde_archivo_temporal(self):
        contenido = (
            "piezas:\n"
            "  - id: x\n"
            "    nombre: X\n"
            "    estado: pendiente\n"
            "    pilar: base\n"
            "    fase: 2\n"
            "    adrs: [ADR-002]\n"
            "decisiones_abiertas: []\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as f:
            f.write(contenido)
            ruta = f.name

        try:
            datos = cargar_estado(ruta)
            self.assertEqual(datos["piezas"][0]["id"], "x")
        finally:
            Path(ruta).unlink()


class ArquitecturaValidacionTests(TestCase):
    """apps/adminpanel/arquitectura.py es la misma validación que corre
    .githooks/pre-commit (vía manage.py validar_arquitectura) — probada acá
    directamente, sin pasar por el hook. Ver ADR-032."""

    def test_arquitectura_real_es_valida(self):
        """Cubre el caso real: ARQUITECTURA.md §6 debe listar exactamente
        los archivos ADR-*.md que existen hoy en docs/decisiones/, en los
        dos sentidos. Corre siempre, no solo cuando ARQUITECTURA.md o una
        ADR cambian — mismo criterio que EstadoValidacionTests para el
        caso inverso."""
        contenido = RUTA_ARQUITECTURA.read_text(encoding="utf-8")
        errores = validar_arquitectura(contenido)
        self.assertEqual(errores, [], f"ARQUITECTURA.md §6 no es válida: {errores}")

    def test_detecta_adr_real_faltante_en_seccion_6(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "ADR-001-primera.md").write_text("x")
            (raiz / "ADR-002-segunda.md").write_text("x")
            contenido = "## 6. Registro de decisiones\n\n- ADR-001: primera.\n"

            errores = validar_arquitectura(contenido, raiz_adrs=raiz)

            self.assertTrue(any("ADR-002" in e for e in errores))

    def test_detecta_renglon_huerfano_en_seccion_6(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "ADR-001-primera.md").write_text("x")
            contenido = "## 6. Registro de decisiones\n\n- ADR-001: primera.\n- ADR-999: no existe.\n"

            errores = validar_arquitectura(contenido, raiz_adrs=raiz)

            self.assertTrue(any("ADR-999" in e for e in errores))

    def test_seccion_completa_pasa(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "ADR-001-primera.md").write_text("x")
            contenido = "## 6. Registro de decisiones\n\n- ADR-001: primera.\n## 7. Otra sección\ntexto.\n"

            errores = validar_arquitectura(contenido, raiz_adrs=raiz)

            self.assertEqual(errores, [])

    def test_no_cuenta_renglones_fuera_de_la_seccion_6(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "ADR-001-primera.md").write_text("x")
            contenido = (
                "## 6. Registro de decisiones\n\n"
                "- ADR-001: primera.\n"
                "## 7. Otra cosa\n\n"
                "- ADR-999: esto no cuenta, está fuera de §6.\n"
            )

            errores = validar_arquitectura(contenido, raiz_adrs=raiz)

            self.assertEqual(errores, [])

    def test_falta_encabezado_seccion_6(self):
        with tempfile.TemporaryDirectory() as tmp:
            errores = validar_arquitectura("sin encabezado acá", raiz_adrs=Path(tmp))

        self.assertTrue(any("Registro de decisiones" in e for e in errores))


class HooksPathActivadoTests(TestCase):
    """ADR-018 documenta que 'git config core.hooksPath .githooks' es
    activación manual por clon, no viaja con git clone — si queda
    desactivada, el hook de pre-commit no protege nada sin avisar. Ver
    ADR-029, agregado de alcance: cierra ese hueco con una línea de test."""

    def test_core_hooks_path_apunta_a_githooks(self):
        config_path = Path(settings.BASE_DIR) / ".git" / "config"
        self.assertTrue(config_path.exists(), f"no se encontró {config_path}")

        valor = None
        en_core = False
        for linea in config_path.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea.startswith("["):
                en_core = linea == "[core]"
                continue
            if en_core and linea.startswith("hooksPath"):
                valor = linea.split("=", 1)[1].strip()
                break

        self.assertEqual(
            valor,
            ".githooks",
            "core.hooksPath no apunta a .githooks — el hook de pre-commit no está activo en este clon "
            "(activación manual por clon, ver ADR-018: 'git config core.hooksPath .githooks')",
        )
