from django.db import models


class StatusNote(models.Model):
    """Modelo mínimo de ejemplo: registra el patrón modelo + ModelAdmin
    que van a seguir las apps futuras de IA CENTRAL. Sin uso funcional real
    todavía.
    """

    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
