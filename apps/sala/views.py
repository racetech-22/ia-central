from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, render

from .models import Chat

es_superusuario = user_passes_test(lambda u: u.is_superuser, login_url="admin:login")


@es_superusuario
def lista_chats(request):
    """Vista andamio (ADR-035): lista los Chat existentes. Sin pantalla de
    creación — los chats se crean desde el admin de Django por ahora."""
    chats = Chat.objects.select_related("proyecto").all()
    return render(request, "sala/lista.html", {"chats": chats})


@es_superusuario
def detalle_chat(request, chat_id):
    """Vista andamio (ADR-035): abre el WebSocket de ese chat y muestra en
    vivo lo que llega por el grupo — no es la pantalla final de la sala
    (pilar1_sala_navegador sigue pendiente)."""
    chat = get_object_or_404(Chat, pk=chat_id)
    return render(request, "sala/detalle.html", {"chat": chat})
