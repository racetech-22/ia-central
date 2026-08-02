"""Tests adversariales de security.py — la única autoridad de la condición de
ADR-017. Cada caso de rechazo se prueba por separado y explícito, no agregado.
"""

from __future__ import annotations

import pytest

from mcp_servers.django_project.security import PathSecurityError, resolve_safe_path


@pytest.fixture
def allowed_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("contenido legítimo\n")
    (root / "subdir").mkdir()
    (root / "subdir" / "archivo.txt").write_text("otro archivo legítimo\n")
    return root


def test_rechaza_traversal_clasico(allowed_root):
    with pytest.raises(PathSecurityError):
        resolve_safe_path("../../../etc/passwd", allowed_root)


def test_rechaza_ruta_absoluta_fuera_de_la_raiz(allowed_root):
    with pytest.raises(PathSecurityError):
        resolve_safe_path("/etc/passwd", allowed_root)


def test_rechaza_symlink_que_escapa_de_la_raiz(allowed_root, tmp_path):
    afuera = tmp_path / "afuera_de_la_raiz.txt"
    afuera.write_text("esto no debería ser legible desde la tool\n")

    symlink_malicioso = allowed_root / "enlace_que_escapa"
    symlink_malicioso.symlink_to(afuera)

    with pytest.raises(PathSecurityError):
        resolve_safe_path("enlace_que_escapa", allowed_root)


def test_rechaza_env_dentro_de_la_raiz(allowed_root):
    (allowed_root / ".env").write_text("SECRET_KEY=no-deberia-leerse\n")

    with pytest.raises(PathSecurityError):
        resolve_safe_path(".env", allowed_root)


def test_rechaza_variante_env_local_dentro_de_la_raiz(allowed_root):
    (allowed_root / ".env.local").write_text("SECRET_KEY=tampoco-esto\n")

    with pytest.raises(PathSecurityError):
        resolve_safe_path(".env.local", allowed_root)


def test_acepta_ruta_legitima_dentro_de_la_raiz(allowed_root):
    resuelto = resolve_safe_path("subdir/archivo.txt", allowed_root)

    assert resuelto == (allowed_root / "subdir" / "archivo.txt").resolve()
    assert resuelto.read_text() == "otro archivo legítimo\n"
