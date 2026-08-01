# ADR-011 - La fuente de verdad se consulta en vivo desde GitHub, no vía Knowledge/Drive estático

Fecha: 2026-07-31
Estado: Aceptada

## Contexto

Al intentar mantener el proyecto "IA CENTRAL" en Claude Desktop actualizado con el estado del repo, se probaron dos vías y ambas fallan estructuralmente para contenido que cambia con cada commit:

1. **Sync de "Knowledge" del proyecto apuntando al repo de GitHub**: mostró 0 archivos de forma persistente. Causa raíz: el repo tenía el default branch en `main`, rama casi huérfana (solo `CLAUDE.md`), mientras todo el contenido real vivía en `master`. Corregido el default branch, pero además la config de la fuente (`branch` fijo en el momento de agregarla) no se actualiza sola si cambia el default de GitHub — hay que quitar y re-agregar la fuente.
2. **Conector de Google Drive**: no permite agregar carpetas completas al proyecto, solo archivos sueltos, y el pegado de URLs de carpeta falla con error de URL no válida. Subiendo archivos individuales manualmente ("Subir desde dispositivo", usando el mapeo local de Drive) sí funciona, pero crea una copia **estática**: no se actualiza cuando Code agrega un ADR nuevo o edita CHANGELOG.md. Además, aunque se lograra usar el conector de Drive en vez de subida manual, la sincronización "en vivo" que ofrece Claude solo aplica a Google Docs nativos — y ADR-010 decidió a propósito subir los archivos como texto plano (no Google Docs), así que tampoco resolvería el problema de fondo.

## Decisión

Cualquier sesión de Claude que tenga acceso a herramientas de fetch web o shell (Cowork, o un chat de claude.ai con búsqueda web activada) debe leer en vivo, al inicio de cualquier tarea sustancial sobre este proyecto, los archivos `README.md`, `CLAUDE.md`, `ARQUITECTURA.md`, `CHANGELOG.md` y `docs/decisiones/ADR-*.md` directamente desde `https://raw.githubusercontent.com/racetech-22/ia-central/master/`, en vez de depender de Knowledge/Files del proyecto en Claude Desktop o de copias en Google Drive. Se agrega una instrucción explícita en este sentido tanto a CLAUDE.md como a las instrucciones del proyecto en Claude Desktop.

## Alternativas descartadas

- **Mantener copias subidas a mano en Knowledge/Files del proyecto**: descartada — se desactualizan en cada commit nuevo, exactamente el problema que se buscaba evitar.
- **Conector de Google Drive para sync de carpeta completa**: descartada — restricción estructural del producto (no soporta carpetas), y su garantía de sync en vivo no cubre Markdown plano.
- **Depender de la memoria entre conversaciones de Claude Desktop** como mecanismo primario de contexto: descartada — solo captura hechos puntuales guardados explícitamente, no el estado completo del repo, y no está disponible de forma consistente en todo tipo de sesión.

## Consecuencias

- En sesiones sin acceso a herramientas de fetch/shell, esta estrategia no aplica: sigue haciendo falta pegar contenido a mano o activar búsqueda web en esa conversación.
- Requiere que el repo permanezca público (o que se conecte un conector de GitHub autenticado si se revierte a privado).
- Resuelto: rama `main` eliminada, `master` (default) ya contiene el conjunto completo.

## Enmienda (2026-08-01): dos capas independientes de rezago, no una

Al verificar en vivo que ADR-012 había quedado aplicado, un fetch a `https://raw.githubusercontent.com/racetech-22/ia-central/master/ARQUITECTURA.md` desde Cowork devolvió una versión desactualizada (sin ADR-010/011/012, con "GitHub privado" en §3). Investigado a fondo, hay **dos capas de caché independientes**, no una sola:

a) **CDN de `raw.githubusercontent.com` (Fastly)**: `cache-control: max-age=300` — hasta 5 minutos de rezago tras un push, por diseño del CDN de GitHub. Verificado con un query param nunca antes usado (timestamp único en nanosegundos): la respuesta seguía siendo `x-cache: HIT` con `source-age` de varios minutos — **el query string no afecta la cache key en este endpoint, agregarlo no evita este rezago**. La única mitigación real para esta capa es esperar unos minutos después de pushear antes de asumir que un fetch trae lo último.

b) **Caché del cliente que hace el fetch**: verificado desde Cowork que su herramienta de fetch deduplica por URL exacta dentro de una sesión (mensaje explícito de la herramienta: "Already fetched ... deduplicated for up to 900s"). Esta capa es independiente de (a) y sí se evita variando la URL — agregar `?v=<sha-del-commit>` (o cualquier valor único) fuerza una lectura nueva del lado del cliente, aunque no tenga ningún efecto sobre el CDN de GitHub.

Se descartó cambiar la estrategia a `api.github.com/repos/.../contents/...` (menor TTL de caché, 60s en vez de 300s, verificado por curl desde el VPS): devuelve vacío desde el fetch de Cowork incluso con el repo público — el motivo exacto no está confirmado, pero el resultado práctico es que no sirve para el caso de uso real. Un `curl` directo sí lo resuelve, pero eso solo ayuda a sesiones que ya corren shell sobre el VPS — que ya tienen el repo clonado y no necesitan esta estrategia en absoluto.

**Conclusión práctica**: la instrucción de ADR-011 se mantiene (`raw.githubusercontent.com`), pero toda sesión que la siga debe (1) agregar un parámetro único a la URL en cada fetch, para evitar la deduplicación del lado del cliente, y (2) tener en cuenta que aun así puede haber hasta ~5 minutos de rezago real del lado del CDN si se acaba de pushear algo — un fetch que devuelve 200 no garantiza que el contenido sea el del último commit.
