# ADR-010 - Sync automático de la documentación a Google Drive vía GitHub Actions

Fecha: 2026-07-31
Estado: Aceptada

## Contexto

ADR-005 ya había resuelto un problema similar (backups de Postgres fuera del VPS, vía `rclone` hacia Google Drive), pero solo para los dumps de la base — la documentación del proyecto (README.md, CLAUDE.md, ARQUITECTURA.md, CHANGELOG.md y `docs/**`) seguía viviendo únicamente en GitHub. Hacía falta una copia adicional, legible directamente en Drive, sin depender de tener acceso al repo o al VPS.

Para autenticar contra la API de Google Drive desde un GitHub Action había dos caminos: una cuenta de servicio de Google, o OAuth2 con una cuenta personal. Se evaluó la cuenta de servicio primero por ser el mecanismo más estándar para automatizaciones sin intervención humana, pero las cuentas de servicio de Google **no tienen cuota de almacenamiento propia** en Drive — solo pueden escribir archivos dentro de Shared Drives, una función que requiere Google Workspace (de pago). La cuenta involucrada acá es un Gmail personal (`domsgofjb@gmail.com`), sin Workspace, así que esa vía no era viable.

## Decisión

Se implementa un GitHub Action (`.github/workflows/sync-drive.yml`) que en cada push a `master` que toque `README.md`, `CLAUDE.md`, `ARQUITECTURA.md`, `CHANGELOG.md` o `docs/**`, corre `.github/scripts/sync_to_drive.py`. El script sube esos archivos tal cual (texto plano, sin convertir a Google Docs) a la carpeta de Drive `ia-central-backups` (id `1dOeSC1D4Lu5NGGvteMb1JF9iehRUr-bQ`), reflejando la estructura de subcarpetas de `docs/`. Si un archivo ya existe en Drive (mismo nombre, misma carpeta), se actualiza en vez de duplicarlo.

La autenticación es OAuth2 con la cuenta personal del usuario (`domsgofjb@gmail.com`), usando credenciales de tipo "Aplicación de escritorio" (client ID + client secret) y un refresh token de larga duración. Las tres credenciales viven como GitHub Secrets: `GDRIVE_CLIENT_ID`, `GDRIVE_CLIENT_SECRET`, `GDRIVE_REFRESH_TOKEN`. El refresh token se generó una sola vez, de forma local, corriendo `get_refresh_token.py` (deliberadamente no versionado — quedó solo en la PC local) con `google-auth-oauthlib`, que hizo el flujo de consentimiento en un navegador y devolvió el token para pegarlo directamente como secret en GitHub.

## Alternativas descartadas

- **Cuenta de servicio de Google**: descartada por la razón de fondo explicada arriba — sin Shared Drive (que requiere Workspace de pago) no tiene dónde escribir archivos con cuota propia. No es una limitación de configuración, es una restricción estructural del producto.
- **Migrar a Google Workspace solo para tener Shared Drives y poder usar cuenta de servicio**: agrega un costo recurrente nuevo únicamente para resolver un problema de autenticación de una automatización de bajo riesgo. Se descarta — el patrón interino equivalente en ADR-005 (rclone + OAuth2 personal para los backups de Postgres) ya estableció que OAuth2 con cuenta personal es un costo/riesgo aceptable para este proyecto en esta etapa.
- **Convertir los archivos a Google Docs al subirlos**: se descarta porque los archivos son Markdown versionado (fuente de verdad en Git, ver CLAUDE.md "Cómo mantener la documentación") — convertirlos a Google Docs los desincroniza de su formato original y invita a que alguien los edite directamente en Drive, que dejaría de ser un espejo fiel del repo.

## Consecuencias

- El refresh token es una credencial de larga duración pero no eterna: si se revoca manualmente (desde la cuenta de Google, sección de apps con acceso) o expira por inactividad prolongada, el workflow empieza a fallar en el paso de autenticación. La única forma de recuperarlo es repetir el flujo local con `get_refresh_token.py` y actualizar el secret `GDRIVE_REFRESH_TOKEN` en GitHub — no hay forma de regenerarlo desde el propio VPS ni desde el Action.
- El scope de OAuth2 usado es `https://www.googleapis.com/auth/drive` (acceso completo a Drive, no acotado a `drive.file` como en ADR-005) — a diferencia del `rclone` de los backups de Postgres, acá no se restringió el scope al mínimo. Si en algún momento se quiere acotar esto, hay que regenerar el refresh token con el scope reducido.
- Igual que ADR-005 con `rclone`/Google Drive para los backups: esto depende de la cuenta personal de Fernando, no de una identidad propia del proyecto. Si más adelante se decide profesionalizar esto (Workspace propio, cuenta de servicio con Shared Drive), esta ADR debería marcarse como superada.
- Si se migra el proyecto a otro servidor (ADR-002), este workflow no depende del VPS en absoluto — corre en GitHub Actions, así que sigue funcionando igual sin cambios, siempre que los tres secrets sigan configurados en el repo de GitHub.
