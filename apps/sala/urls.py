from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista_chats, name="lista_chats"),
    path("<int:chat_id>/", views.detalle_chat, name="detalle_chat"),
]
