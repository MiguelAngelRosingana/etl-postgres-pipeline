import os

import pytest
from sqlalchemy import text

from etl.db import aplicar_sql, crear_engine


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integracion: necesita PostgreSQL (variable TEST_DATABASE_URL)"
    )


@pytest.fixture(scope="session")
def engine():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Define TEST_DATABASE_URL para ejecutar los tests de integración")
    eng = crear_engine(url)
    yield eng
    eng.dispose()


@pytest.fixture()
def bd_limpia(engine):
    """Borra y recrea el esquema antes de cada test. ¡Solo usar con una base de datos de pruebas!"""
    with engine.begin() as conn:
        for esquema in ("stg", "core", "etl"):
            conn.execute(text(f"DROP SCHEMA IF EXISTS {esquema} CASCADE"))
    aplicar_sql(engine)
    return engine
