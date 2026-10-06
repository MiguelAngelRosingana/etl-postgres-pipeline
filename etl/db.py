"""Conexión a PostgreSQL y aplicación del esquema."""
from pathlib import Path

from sqlalchemy import Engine, create_engine

from etl.config import CARPETA_SQL


def crear_engine(url: str) -> Engine:
    # pool_pre_ping: comprueba la conexión antes de usarla y evita errores por conexiones caídas
    return create_engine(url, pool_pre_ping=True)


def aplicar_sql(engine: Engine, carpeta: Path = CARPETA_SQL) -> list[str]:
    """Ejecuta los .sql de la carpeta por orden alfabético, en una sola transacción."""
    aplicados = []
    with engine.begin() as conn:
        for archivo in sorted(carpeta.glob("*.sql")):
            conn.exec_driver_sql(archivo.read_text(encoding="utf-8"))
            aplicados.append(archivo.name)
    return aplicados
