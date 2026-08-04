import hashlib
import secrets


def generate_connection_token() -> str:
    """Token de conexión en texto plano — se muestra una sola vez, nunca se
    persiste así (ver Proyecto.connection_token_hash)."""
    return secrets.token_urlsafe(32)


def hash_connection_token(token: str) -> str:
    """SHA-256 hex digest — lo único que se guarda en la base."""
    return hashlib.sha256(token.encode()).hexdigest()
