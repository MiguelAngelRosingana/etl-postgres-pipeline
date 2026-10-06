"""Configuración leída de variables de entorno (nunca credenciales en el código)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CARPETA_SQL = Path(__file__).resolve().parent.parent / "sql"


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("Falta DATABASE_URL. Copia .env.example a .env y ajústalo.")
    return url
