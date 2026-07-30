from django.contrib import admin

from .models import StatusNote


@admin.register(StatusNote)
class StatusNoteAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at")
    search_fields = ("title", "body")
