"""Gestión de la conexión a PostgreSQL vía SQLAlchemy."""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from src.config import DATABASE_URL


def get_engine() -> Engine:
    """Crea y retorna un Engine SQLAlchemy con pool_pre_ping habilitado.

    Returns:
        Engine configurado para PostgreSQL.
    """
    return create_engine(DATABASE_URL, pool_pre_ping=True, future=True)


@contextmanager
def get_connection(engine: Engine) -> Generator[Connection, None, None]:
    """Context manager que entrega una conexión y hace commit o rollback.

    Args:
        engine: Engine SQLAlchemy activo.

    Yields:
        Conexión lista para ejecutar sentencias.
    """
    with engine.begin() as conn:
        yield conn


def execute_sql(conn: Connection, sql: str, params: dict | None = None) -> None:
    """Ejecuta una sentencia SQL con parámetros opcionales.

    Args:
        conn: Conexión SQLAlchemy activa.
        sql: Sentencia SQL a ejecutar.
        params: Parámetros para la sentencia (opcional).
    """
    conn.execute(text(sql), params or {})
