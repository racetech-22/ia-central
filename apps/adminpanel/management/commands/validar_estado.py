import sys

import yaml
from django.core.management.base import BaseCommand

from apps.adminpanel.estado import RUTA_ESTADO, cargar_estado, validar_estado


class Command(BaseCommand):
    help = (
        "Valida docs/estado.yml (ADR-029): esquema, que cada ADR referenciada "
        "exista como archivo real en docs/decisiones/, y que exista en disco "
        "cada artefacto declarado por una pieza marcada 'construido'. No "
        "ejecuta ningún comando de 'prueba' — ese campo es solo declarativo."
    )

    def handle(self, *args, **options):
        try:
            datos = cargar_estado()
        except FileNotFoundError:
            self.stderr.write(f"no existe {RUTA_ESTADO}")
            sys.exit(1)
        except yaml.YAMLError as exc:
            self.stderr.write(f"docs/estado.yml no es YAML válido: {exc}")
            sys.exit(1)

        errores = validar_estado(datos)
        if errores:
            self.stderr.write(f"docs/estado.yml no pasa la validación ({len(errores)} error/es):")
            for error in errores:
                self.stderr.write(f"  - {error}")
            sys.exit(1)

        self.stdout.write(self.style.SUCCESS("docs/estado.yml válido"))
