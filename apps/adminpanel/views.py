from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render


@user_passes_test(lambda u: u.is_superuser, login_url="admin:login")
def mapa(request):
    """Hoja de ruta de IA CENTRAL: página estática, sin consultas a la base."""
    return render(request, "adminpanel/mapa.html")
