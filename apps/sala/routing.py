from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"^ws/sala/(?P<chat_id>[0-9]+)/$", consumers.SalaConsumer.as_asgi()),
]
