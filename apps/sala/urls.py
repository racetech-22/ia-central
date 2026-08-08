from django.urls import path

from . import views

urlpatterns = [
    path("", views.vista_sala, name="sala"),
    path("chat/<int:chat_id>/", views.detalle_chat, name="detalle_chat"),
    path("chat/nuevo/", views.crear_chat, name="crear_chat"),
]
