"""
Sincroniza documentos del repo ia-central hacia una carpeta de Google Drive.

Fuente:
  - Los 4 archivos raiz: README.md, CLAUDE.md, ARQUITECTURA.md, CHANGELOG.md
  - Todo el contenido de docs/ (recursivo, con subcarpetas)

Destino:
  - Carpeta de Drive indicada por GDRIVE_FOLDER_ID (ia-central-backups).
  - Los 4 archivos raiz van directo en esa carpeta.
  - docs/ se refleja como subcarpeta "docs" dentro de esa carpeta,
    preservando la misma estructura de subcarpetas del repo.

Los archivos se suben tal cual (texto plano), sin convertir a Google Docs.
Si un archivo ya existe en Drive (mismo nombre, misma carpeta), se actualiza
su contenido en vez de crear un duplicado.
"""

import os
import mimetypes
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
ROOT_FOLDER_ID = os.environ["GDRIVE_FOLDER_ID"]

ROOT_FILES = ["README.md", "CLAUDE.md", "ARQUITECTURA.md", "CHANGELOG.md"]
DOCS_DIR = "docs"

EXTRA_MIME_TYPES = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".yml": "text/yaml",
    ".yaml": "text/yaml",
    ".json": "application/json",
}

creds = Credentials(
    token=None,
    refresh_token=os.environ["GDRIVE_REFRESH_TOKEN"],
    token_uri="https://oauth2.googleapis.com/token",
    client_id=os.environ["GDRIVE_CLIENT_ID"],
    client_secret=os.environ["GDRIVE_CLIENT_SECRET"],
    scopes=SCOPES,
)
creds.refresh(Request())
drive = build("drive", "v3", credentials=creds)

_folder_cache = {}


def guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in EXTRA_MIME_TYPES:
        return EXTRA_MIME_TYPES[ext]
    mime_type, _ = mimetypes.guess_type(str(path))
    return mime_type or "application/octet-stream"


def find_child(name: str, parent_id: str, is_folder: bool = False):
    mime_filter = (
        " and mimeType = 'application/vnd.google-apps.folder'" if is_folder else ""
    )
    safe_name = name.replace("'", "\\'")
    q = f"name = '{safe_name}' and '{parent_id}' in parents and trashed = false{mime_filter}"
    res = drive.files().list(q=q, fields="files(id, name)", spaces="drive").execute()
    files = res.get("files", [])
    return files[0]["id"] if files else None


def get_or_create_folder(name: str, parent_id: str) -> str:
    key = (parent_id, name)
    if key in _folder_cache:
        return _folder_cache[key]
    existing = find_child(name, parent_id, is_folder=True)
    if existing:
        _folder_cache[key] = existing
        return existing
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = drive.files().create(body=metadata, fields="id").execute()
    _folder_cache[key] = folder["id"]
    print(f"Carpeta creada en Drive: {name}")
    return folder["id"]


def upload_file(local_path: Path, parent_id: str):
    mime_type = guess_mime(local_path)
    media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=False)
    existing_id = find_child(local_path.name, parent_id)
    if existing_id:
        drive.files().update(fileId=existing_id, media_body=media).execute()
        print(f"Actualizado: {local_path}")
    else:
        metadata = {"name": local_path.name, "parents": [parent_id]}
        drive.files().create(body=metadata, media_body=media, fields="id").execute()
        print(f"Subido: {local_path}")


def sync_root_files():
    for name in ROOT_FILES:
        path = Path(name)
        if path.exists():
            upload_file(path, ROOT_FOLDER_ID)
        else:
            print(f"Aviso: no encontrado en el repo, se omite: {name}")


def sync_docs_dir():
    docs_path = Path(DOCS_DIR)
    if not docs_path.exists():
        print(f"Aviso: no existe la carpeta {DOCS_DIR}/ en este checkout, se omite.")
        return

    drive_docs_root = get_or_create_folder(DOCS_DIR, ROOT_FOLDER_ID)

    for dirpath, _dirnames, filenames in os.walk(docs_path):
        rel_dir = Path(dirpath).relative_to(docs_path)
        parent_id = drive_docs_root
        if str(rel_dir) != ".":
            for part in rel_dir.parts:
                parent_id = get_or_create_folder(part, parent_id)
        for filename in filenames:
            upload_file(Path(dirpath) / filename, parent_id)


if __name__ == "__main__":
    sync_root_files()
    sync_docs_dir()
    print("Sincronizacion completa.")
