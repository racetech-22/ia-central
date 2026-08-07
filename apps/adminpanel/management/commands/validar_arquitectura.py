import sys

from django.core.management.base import BaseCommand

from apps.adminpanel.arquitectura import RUTA_ARQUITECTURA, validar_arquitectura


class Command(BaseCommand):
    help = (
        "Valida que ARQUITECTURA.md §6 (Registro de decisiones) coincida con "
        "los archivos ADR reales de docs/decisiones/, en los dos sentidos "
        "(ADR-032)."
    )

    def handle(self, *args, **options):
        try:
            contenido = RUTA_ARQUITECTURA.read_text(encoding="utf-8")
        except FileNotFoundError:
            self.stderr.write(f"no existe {RUTA_ARQUITECTURA}")
            sys.exit(1)

        errores = validar_arquitectura(contenido)
        if errores:
            self.stderr.write(f"ARQUITECTURA.md §6 no pasa la validación ({len(errores)} error/es):")
            for error in errores:
                self.stderr.write(f"  - {error}")
            sys.exit(1)

        self.stdout.write(self.style.SUCCESS("ARQUITECTURA.md §6 válido"))
