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

## Enmienda (2026-08-02): los nombres de archivo de las ADR no son deducibles, agregado `docs/decisiones/INDEX.md`

Verificado en una sesión de Cowork sin navegador conectado: asumir que cada ADR se llama `ADR-NNN.md` es incorrecto — cada archivo lleva un slug descriptivo (`ADR-001-arquitectura-base.md`, `ADR-011-fuente-de-verdad-en-vivo.md`, etc.), no documentado hasta ahora en ningún lado. Un fetch a un nombre adivinado devuelve 404, y eso no se distingue de una respuesta vacía por otra causa — sin señal de error explícita.

Esto agrava el problema ya documentado en la enmienda anterior: el fallback natural para resolver nombres reales, `api.github.com/repos/.../contents/docs/decisiones`, ya estaba confirmado que devuelve vacío desde herramientas de fetch como la de Cowork. Sin acceso a navegador, una sesión fetch-only queda sin ninguna vía para descubrir los nombres reales — tuvo que resolverse en la práctica navegando la vista de archivos de GitHub con herramientas de navegador, un fallback que no está disponible en todo tipo de sesión (p. ej. claude.ai con solo búsqueda web, el otro caso que esta ADR dice cubrir).

**Decisión**: se agrega `docs/decisiones/INDEX.md`, en ruta fija, con una tabla ADR → nombre de archivo. Cualquier sesión fetch-only debe leer ese índice primero (mismo mecanismo de cache-busting que el resto: `?v=<único>`) y de ahí construir la URL real de cada ADR, en vez de asumir el patrón `ADR-NNN.md`. Se agrega la instrucción correspondiente a CLAUDE.md.

**Mantenimiento**: `INDEX.md` se actualiza en el mismo commit que agrega cualquier ADR nueva — mismo hábito ya exigido para ARQUITECTURA.md §6 y CHANGELOG.md, no un paso adicional real. Vale la pena agregarlo explícitamente al alcance de `scripts/adr_audit.sh` (ADR-014) la próxima vez que se toque ese script.

## Enmienda (2026-08-03): el cache-busting con `?v=` ya no es confiable — reemplazado, no complementado

Hallazgo en vivo durante la revisión de ADR-021: tres pedidos consecutivos a `raw.githubusercontent.com` con un parámetro `?v=<timestamp único cada vez>` en cada uno devolvieron el mismo contenido desactualizado, con header `x-cache: HIT` y `source-age` creciente (42s, 44s, 46s) — el CDN de GitHub (Fastly) está ignorando el query string para el cálculo de la clave de caché en esta ruta, al menos en esta fecha. Esto contradice directamente lo que la enmienda del 2026-08-01 documentó como mitigación de la capa (b) (deduplicación del lado del cliente) — el mecanismo sigue sirviendo para esa capa específica, pero ya no es un método confiable en general: puede fallar en silencio, sin ningún indicio de que el contenido devuelto no es el actual.

Lo que sí se verificó confiable en la misma sesión: `api.github.com/repos/racetech-22/ia-central/commits/<rama-o-master>` devuelve el SHA real del HEAD sin el mismo problema de staleness.

**Nuevo protocolo — reemplaza al de `?v=`, no lo complementa:**

1. Pedir primero `https://api.github.com/repos/racetech-22/ia-central/commits/<rama-o-master>` para obtener el SHA real y actual del commit.
2. Pedir el archivo vía `https://raw.githubusercontent.com/racetech-22/ia-central/<SHA>/<ruta>` — anclado al SHA exacto, **nunca al nombre de la rama**. El contenido de un SHA fijo es inmutable: aunque el CDN lo cachee para siempre, sigue siendo correcto por definición. No hace falta ningún cache-busting contra una URL anclada a un commit específico, porque no hay nada que "vencer" — esa URL nunca va a servir otro contenido.

Esto también resuelve, de paso, la lectura de `docs/decisiones/INDEX.md` y de cualquier ADR puntual: se piden con el mismo SHA obtenido en el paso 1, no con `?v=` sobre la URL de `master`.

La limitación de la enmienda anterior sobre `api.github.com/repos/.../contents/...` (devuelve vacío desde el fetch de Cowork) sigue vigente y no se ve afectada: el endpoint nuevo que se usa acá es `/commits/<ref>`, no `/contents/...` — son rutas distintas de la misma API, verificar cada una por separado antes de asumir que comparten el mismo problema.
