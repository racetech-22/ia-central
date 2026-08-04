from django.contrib import admin
from django.urls import path

from apps.adminpanel import views as adminpanel_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("mapa/", adminpanel_views.mapa, name="mapa"),
]
