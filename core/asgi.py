import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

# get_asgi_application() se llama antes de importar cualquier código que
# dependa del registro de apps de Django (ver documentación de Channels),
# aunque por ahora ProtocolTypeRouter solo tenga la rama "http" — las rutas
# de websocket son la subtarea siguiente (ADR-025 §9.7).
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # "websocket": ..., subtarea siguiente.
    }
)
