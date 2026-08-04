from django.db import migrations


def crear_proyecto_ia_central(apps, schema_editor):
    Proyecto = apps.get_model("sala", "Proyecto")
    Proyecto.objects.create(
        project_key="ia-central",
        nombre="IA CENTRAL",
        destino_tipo="nativo",
        dominio="aicentral.network",
    )


def borrar_proyecto_ia_central(apps, schema_editor):
    Proyecto = apps.get_model("sala", "Proyecto")
    Proyecto.objects.filter(project_key="ia-central").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sala", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(crear_proyecto_ia_central, borrar_proyecto_ia_central),
    ]
