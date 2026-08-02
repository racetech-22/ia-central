# ADR-002 - Repositorio en GitHub y VPS dedicado nuevo en Contabo

Fecha: 2026-07-30
Estado: Aceptada

## Contexto

Fernando ya tiene cuenta en GitHub y VPS existentes en Contabo con otros proyectos en producción. Había que decidir dónde vive el código/documentación fuente de verdad, y si IA CENTRAL corre en un VPS ya existente o en uno nuevo.

## Decisión

- Repositorio: GitHub privado (ia-central), clonado tanto en el VPS de IA CENTRAL como en la máquina local de Fernando. El repo es la fuente de verdad versionada para código, ARQUITECTURA.md, ADRs y CHANGELOG.md. **Nota (2026-07-31):** el repo pasó a ser público — ver ADR-011, que documenta por qué (fetch en vivo de la documentación desde `raw.githubusercontent.com`). El resto de esta decisión (VPS dedicado, GitHub como fuente de verdad) sigue vigente sin cambios.
- VPS: uno nuevo y dedicado en Contabo, exclusivo para IA CENTRAL. No se reutiliza ninguno de los VPS existentes de Fernando.
- Especificación contratada: Cloud VPS 6, 6 vCPU, 12GB RAM, 200GB SSD NVMe, región EU, Ubuntu 24.04, Auto Backup activado, plazo mensual.
- Acceso futuro a los servidores existentes: cuando IA CENTRAL esté más maduro, se conectará a los proyectos que Fernando ya tiene en otros servidores mediante MCP/SSH de solo lectura por defecto, sin necesidad de migrarlos.

## Alternativas descartadas

- Reutilizar un VPS existente: más barato a corto plazo, pero arriesga la estabilidad de proyectos ya en producción y complica medir el consumo real de IA CENTRAL. Descartado.
- Contratar de entrada un VPS de alta gama (32GB+): sobreprovisiona recursos que solo serían necesarios si se corren modelos locales grandes, algo que se difiere hasta que sea necesario. Descartado por ahora.

## Consecuencias

- Se generó una clave SSH dedicada en el VPS (deploy key) y se agregó con acceso de lectura/escritura al repo en GitHub, sin usar la clave personal de Fernando.
- El acceso a otros servidores se implementa como conectores de solo lectura, revisables antes de otorgar cualquier permiso de escritura.

## Enmienda 2026-08-02: no se mantiene un clon local en la máquina de Fernando

La auditoría de solo lectura del 2026-08-02 detectó que ARQUITECTURA.md §3 y CLAUDE.md afirmaban que el repo estaba "clonado igual en el VPS y en la máquina local de Fernando", sin que exista ninguna entrada en CHANGELOG.md que documente la creación de ese clon — una afirmación no verificada.

Se decide no mantener ese clon local: GitHub y el VPS ya son dos copias completas con historia de Git íntegra, y el snapshot diario de VM de Contabo (ver ARQUITECTURA.md §3) cubre el escenario de pérdida total del VPS. Un clon local adicional, sin disciplina de `git pull` regular, es un riesgo de desactualización silenciosa más que una protección real — mismo patrón que ya falló una vez con el sync de Knowledge/Drive de Claude Desktop (ver ADR-011). Se corrige la redacción de ARQUITECTURA.md §3 y CLAUDE.md en consecuencia.
