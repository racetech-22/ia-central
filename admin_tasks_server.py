"""Sidecar HTTP mínimo para tareas administrativas de Django (ver ADR-023).

Alternativa a exec-dentro-de-`web`-vía-Docker (ADR-022, descartada porque el
proxy de la API de Docker no puede aislar `exec` de crear/borrar
contenedores): este servicio corre con la MISMA imagen que `web` (mismo
Dockerfile, mismo código, mismas dependencias), conectado a `db` por la red
interna igual que `web` — nunca toca el socket ni la API de Docker. Su única
capacidad es correr dos comandos fijos de Django management contra la base
de datos real. Blast radius si se compromete: como mucho, lo que la propia
app Django ya puede hacer contra su base — nada a nivel de host ni de otros
contenedores.

Sin Flask/FastAPI ni ninguna dependencia nueva — `http.server` de la
librería estándar alcanza para dos endpoints fijos, sin parámetros
aceptados del llamador. Nunca publicado en `docker-compose.yml` — solo
alcanzable por la red interna de Docker Compose. El token de
`Authorization` es defensa en profundidad, no la única barrera.
"""

from __future__ import annotations

import hmac
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "0.0.0.0"
PORT = 8100
MAX_OUTPUT_BYTES = 200_000

# Comandos fijos, nunca parametrizables desde el request — el llamador no
# puede elegir ni modificar qué se ejecuta, solo cuál de estas dos rutas fijas
# invocar.
#
# `test apps` (no `test` a secas): el descubrimiento por defecto de
# `manage.py test` recorre todo /app, incluyendo `mcp_servers/django_project/
# tests/` — una suite de pytest ajena a Django que falla al importarse acá
# (falta pytest/anyio en esta imagen, y no tiene por qué estar: no es la
# suite de este servicio). Acotado a `apps` (el paquete real de las apps de
# Django, ver core/settings.py INSTALLED_APPS) para correr solo los tests del
# proyecto Django, verificado que da "0 tests ran" limpio hoy (sin tests
# propios todavía) en vez de errores de import de un paquete no relacionado.
COMMANDS: dict[str, list[str]] = {
    "/run-migrations": ["python", "manage.py", "migrate"],
    "/run-tests": ["python", "manage.py", "test", "apps"],
}


def _run_command(argv: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        argv,
        cwd="/app",
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    encoded = output.encode("utf-8")
    if len(encoded) > MAX_OUTPUT_BYTES:
        truncated = encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
        output = truncated + f"\n\n[TRUNCADO: salida original de {len(encoded)} bytes]"
    return result.returncode, output


class Handler(BaseHTTPRequestHandler):
    def _respond(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _unauthorized(self) -> bool:
        expected = os.environ.get("ADMIN_TASKS_TOKEN")
        auth_header = self.headers.get("Authorization", "")
        provided = auth_header[len("Bearer "):] if auth_header.startswith("Bearer ") else ""
        if not expected or not hmac.compare_digest(provided, expected):
            self._respond(401, b"401 Unauthorized\n")
            return True
        return False

    def do_POST(self) -> None:
        if self._unauthorized():
            return

        argv = COMMANDS.get(self.path)
        if argv is None:
            self._respond(404, b"404 Not Found\n")
            return

        exit_code, output = _run_command(argv)
        body = f"EXIT_CODE={exit_code}\n{output}".encode("utf-8")
        self._respond(200, body)

    def do_GET(self) -> None:
        self._respond(404, b"404 Not Found\n")

    do_PUT = do_GET
    do_DELETE = do_GET
    do_PATCH = do_GET
    do_HEAD = do_GET


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.serve_forever()
