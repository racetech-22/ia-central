# ADR-005 - Sync de backups a Google Drive vía rclone (implementación interina)

Fecha: 2026-07-30
Estado: Aceptada (interina — reemplazar en Fase 5)

## Contexto

ADR-004 dejó documentado que los dumps de `pg_dump` (`scripts/backup_postgres.sh`) quedan solo en el propio VPS: si el servidor se pierde por completo, se pierden con él, dependiendo únicamente del Auto Backup de VM de Contabo (ADR-002) como red de contención. Hacía falta un destino de backup fuera del VPS.

## Decisión

Se instala `rclone` (binario estático en `~/.local/bin`, sin sudo) y se configura un remoto `gdrive` (Google Drive, scope `drive.file` — solo archivos creados por rclone, no acceso al resto del Drive de Fernando) autorizado con la cuenta personal de Fernando vía el flujo headless de rclone (`rclone authorize` corrido en una máquina con navegador, ver más abajo). `scripts/backup_postgres.sh` corre `rclone copy` (nunca `sync`, para no arriesgar borrar nada en el remoto) hacia `gdrive:ia-central-backups/postgres/` después de cada dump local exitoso. Si el paso de rclone falla (red, cuota, token vencido), el script no aborta ni marca error: el backup local ya se guardó, esto es solo una copia adicional.

**Esto es explícitamente una implementación interina, no la solución final.** El destino del backup (hoy: Google Drive personal de Fernando) y las credenciales (hoy: token OAuth de rclone en `~/.config/rclone/rclone.conf`, un archivo suelto en el VPS) deben migrar a ser una configuración gestionada desde el panel administrativo real de IA CENTRAL (Fase 5, ver ARQUITECTURA.md §4) — con el destino y las credenciales visibles/editables ahí, no fijos para siempre en un script y un archivo de config sueltos en el filesystem del VPS. Cuando el panel administrativo exista, esta ADR debe marcarse como superada y reemplazarse por la decisión correspondiente.

## Alternativas descartadas

- **Dejarlo sin resolver hasta que exista el panel administrativo (Fase 5)**: más "correcto" arquitectónicamente, pero deja el conocimiento del proyecto sin ninguna copia fuera del VPS mientras tanto, en contra del principio de portabilidad de ADR-001. Se prioriza tener *algo* fuera del VPS ahora, aceptando que es temporal.
- **Backend de backup distinto (S3/Backblaze/etc.) en vez de Google Drive**: requeriría dar de alta una cuenta/servicio nuevo. Se usa Google Drive porque Fernando ya tiene la cuenta y no hay fricción de setup adicional — coherente con que esto es interino y se va a reemplazar de todas formas.
- **Scope `drive` completo en vez de `drive.file`**: `drive.file` limita el acceso de la credencial solo a los archivos que rclone crea, no a todo el Drive personal de Fernando. Se prioriza el acceso mínimo necesario incluso en una solución interina.

## Consecuencias

- El token OAuth vive en `~/.config/rclone/rclone.conf` en el VPS, fuera del repositorio (no versionado, no debe versionarse). Si se migra el proyecto a otro servidor (ADR-002), hay que rehacer la autorización de rclone ahí.
- **Riesgo conocido**: el remoto usa el `client_id` compartido por defecto de rclone (no se configuró uno propio), y rclone advierte en cada ejecución que ese client_id compartido "se está retirando y va a dejar de funcionar durante 2026". El sync a Drive puede romperse sin ningún cambio de nuestro lado. Si eso pasa antes de llegar a Fase 5, el fix rápido es crear un client_id propio en Google Cloud Console y correr `rclone config update gdrive client_id ... client_secret ...` — pero dado que esta ADR ya es interina, probablemente convenga resolverlo directamente como parte de la migración a Fase 5 en vez de parchear esto dos veces.
- El remoto `gdrive:ia-central-backups/postgres/` acumula todos los dumps sin retención propia (a diferencia de los 14 días locales de ADR-004) porque se usa `rclone copy`, no `sync`. Puede crecer indefinidamente hasta que se agregue una política de retención remota — aceptado por ahora, revisar si se vuelve un problema de cuota.
- Esta ADR queda explícitamente marcada como reemplazable: cuando el panel administrativo (Fase 5) gestione destino/credenciales de backup, esta implementación (script + rclone.conf sueltos) debe desarmarse.
