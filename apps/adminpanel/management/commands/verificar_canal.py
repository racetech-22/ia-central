import asyncio
import sys

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.management.base import BaseCommand

# Cruza brpop_timeout=5 (RedisChannelLayer, ver ADR-037) dos veces.
DURACION_SEGUNDOS = 12


class Command(BaseCommand):
    help = (
        "Prueba una recepción bloqueante de más de 5s contra el channel "
        "layer REAL (el de settings.CHANNEL_LAYERS, no "
        "channels.layers.InMemoryChannelLayer). Este comando existe porque "
        "la suite de tests usa un channel layer en memoria y por eso dio "
        "32/32 en verde el 2026-08-08 con el WebSocket roto en producción "
        "(ver ADR-037): RedisChannelLayer.receive() tiraba "
        "redis.exceptions.TimeoutError cada ~5s por el default de "
        "socket_timeout de redis-py>=8.0.0, sin que ningún test lo "
        "detectara. Sale 0 si la espera completa sin ninguna excepción "
        "real del channel layer; distinto de cero si salta cualquiera."
    )

    async def _esperar(self):
        channel_layer = get_channel_layer()
        canal = await channel_layer.new_channel()
        # Nadie manda nada a este canal a propósito: el objetivo es probar
        # que receive() puede esperar más de 5s sin que el channel layer
        # mismo la tumbe, no que llegue un mensaje. Que la espera se agote
        # por nuestro propio límite (asyncio.TimeoutError, que NO es
        # subclase de redis.exceptions.TimeoutError — verificado antes de
        # escribir esto) es el resultado esperado y correcto.
        try:
            await asyncio.wait_for(channel_layer.receive(canal), timeout=DURACION_SEGUNDOS)
        except asyncio.TimeoutError:
            return

    def handle(self, *args, **options):
        try:
            async_to_sync(self._esperar)()
        except Exception as exc:
            self.stderr.write(f"verificar_canal: excepción real del channel layer: {exc!r}")
            sys.exit(1)

        self.stdout.write(
            self.style.SUCCESS(
                f"verificar_canal: {DURACION_SEGUNDOS}s de espera sin excepciones del channel layer"
            )
        )
