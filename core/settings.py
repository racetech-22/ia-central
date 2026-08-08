"""
Configuración de Django para el proyecto core (IA CENTRAL).

Todos los valores sensibles o dependientes del entorno se leen de variables
de entorno (ver env.example) para que el mismo código corra igual en local,
en el VPS, o en cualquier servidor al que se migre el proyecto.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-dev-only-change-me")

DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

# Nginx (fuera de Docker, ver ADR-003) hace de proxy TLS y reenvía este header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Campo cifrado de credenciales de proyecto de la sala (ADR-025 punto 8).
# Sin default: apps/sala/fields.py falla al arrancar si falta o es inválida.
CREDENTIALS_ENCRYPTION_KEY = os.environ.get("CREDENTIALS_ENCRYPTION_KEY")

INSTALLED_APPS = [
    # daphne va primero, antes de django.contrib.staticfiles: si no, su
    # comando `runserver` con soporte ASGI no toma precedencia sobre el de
    # staticfiles (ver ADR-026).
    "daphne",
    "channels",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.adminpanel",
    "apps.sala",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"
ASGI_APPLICATION = "core.asgi.application"

# Servicio `redis` de docker-compose.yml — solo red interna, sin ports:
# (ADR-025 §9.7, ADR-026). Rutas de websocket construidas en ADR-035.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            # socket_timeout=10 es obligatorio con redis-py>=8.0.0, y tiene
            # que ser mayor que 5. Verificado contra el código fuente real
            # de channels_redis==4.3.0: RedisChannelLayer.brpop_timeout = 5
            # (atributo de clase), y receive_single() hace
            # "while content is None: content = await self._brpop_with_clean(
            # ..., timeout=self.brpop_timeout)" sin try/except alrededor —
            # ese bucle asume que agotar el timeout de BRPOP/BZPOPMIN
            # devuelve None para seguir esperando, nunca que lanza una
            # excepción. redis-py 8.0.0 cambió el default de su propio
            # socket_timeout a 5s; si el socket corta en 5s o menos, el
            # timeout de socket gana la carrera contra el timeout del
            # comando y la excepción sube sin capturar, tumbando el
            # WebSocket. Error real observado en este VPS el 2026-08-08 (ver
            # CHANGELOG.md) y documentado en
            # https://github.com/django/channels_redis/issues/422, mismo
            # traceback exacto — channels_redis 4.3.0 todavía no lo aplica
            # solo.
            "hosts": [{"host": "redis", "port": 6379, "socket_timeout": 10}],
        },
    },
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "ia_central"),
        "USER": os.environ.get("POSTGRES_USER", "ia_central"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "ia_central"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
