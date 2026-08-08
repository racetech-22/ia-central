from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Chat, Proyecto

es_superusuario = user_passes_test(lambda u: u.is_superuser, login_url="admin:login")


@es_superusuario
def vista_sala(request):
    """La Sala (ADR-035, enmienda 2026-08-08): lista los proyectos activos
    con sus chats y un formulario de alta por proyecto. Los chats se crean
    acá, no en el admin de Django — el admin queda como editor de base de
    datos, con Proyecto como única entidad editable ahí."""
    proyectos = Proyecto.objects.filter(activo=True).prefetch_related("chats")
    return render(request, "sala/lista.html", {"proyectos": proyectos})


@es_superusuario
@require_POST
def crear_chat(request):
    """Solo POST, con CSRF. consultor_session_id queda vacío: lo fija el
    Consultor cuando exista, no se inventa acá."""
    proyecto = get_object_or_404(Proyecto, pk=request.POST.get("proyecto_id"), activo=True)
    chat = Chat.objects.create(
        proyecto=proyecto,
        titulo=request.POST.get("titulo", ""),
    )
    return redirect("detalle_chat", chat_id=chat.id)


@es_superusuario
def detalle_chat(request, chat_id):
    """Vista andamio (ADR-035): abre el WebSocket de ese chat y muestra en
    vivo lo que llega por el grupo — no es la pantalla final de la sala
    (pilar1_sala_navegador sigue pendiente)."""
    chat = get_object_or_404(Chat, pk=chat_id)
    return render(request, "sala/detalle.html", {"chat": chat})
