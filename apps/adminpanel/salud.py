"""Chequeo de salud del sistema vivo (ADR-037) — a diferencia de
validar_estado/validar_arquitectura (ADR-029/ADR-032), que miden archivos
del repo, esto mide el proceso corriendo: qué SHA tiene horneado, si
Postgres responde, si el channel layer de Redis hace un viaje de ida y
vuelta real. Público a propósito (ver ADR-037): no expone datos de
negocio, el SHA no es secreto (el repo ya es público, ADR-011).
"""

import os
import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import connection

GIT_SHA_DESCONOCIDO = "desconocido"


def sha_actual():
    return os.environ.get("GIT_SHA", GIT_SHA_DESCONOCIDO)


def verificar_db():
    """Consulta trivial contra Postgres — True si responde, False si no."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:
        return False


def verificar_redis():
    """Ida y vuelta real por el channel layer configurado en settings (el
    mismo que usa SalaConsumer) — no un PING a Redis. Manda un mensaje a un
    canal propio efímero y lo vuelve a leer; si el channel layer no
    completa el viaje (el mismo bug de ADR-037: RedisChannelLayer.receive()
    tirando redis.exceptions.TimeoutError), esto lo detecta."""

    async def _viaje_ida_y_vuelta():
        channel_layer = get_channel_layer()
        canal = await channel_layer.new_channel()
        marca = uuid.uuid4().hex
        await channel_layer.send(canal, {"type": "salud.ping", "marca": marca})
        recibido = await channel_layer.receive(canal)
        return recibido.get("marca") == marca

    try:
        return async_to_sync(_viaje_ida_y_vuelta)()
    except Exception:
        return False


def estado_de_salud():
    """Devuelve (dict_json, sano). El SHA no participa en "sano": eso lo
    evalúa scripts/chequeo_despliegue.sh comparando contra origin/master,
    algo que el proceso corriendo no puede juzgar por sí mismo — acá solo
    se reporta el hecho."""
    db_ok = verificar_db()
    redis_ok = verificar_redis()
    sano = db_ok and redis_ok
    return (
        {
            "sha": sha_actual(),
            "db": db_ok,
            "redis": redis_ok,
        },
        sano,
    )
