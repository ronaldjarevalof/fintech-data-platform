"""Configuración del pipeline: carga variables de entorno y define paths."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB: str = os.getenv("POSTGRES_DB", "tumipay")
POSTGRES_USER: str = os.getenv("POSTGRES_USER", "etl_user")
POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "tumipay")

DATABASE_URL: str = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

DATA_RAW_PATH: Path = Path(os.getenv("DATA_RAW_PATH", "/app/data/raw"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
FECHA_CORTE_ENV: str = os.getenv("FECHA_CORTE", "auto")

# Archivos fuente esperados
CSV_CLIENTES: Path = DATA_RAW_PATH / "clientes.csv"
CSV_CREDITOS: Path = DATA_RAW_PATH / "creditos.csv"
CSV_PAGOS: Path = DATA_RAW_PATH / "pagos.csv"

# Rango del calendario para dim_tiempo
DIM_TIEMPO_DESDE = "2023-01-01"
DIM_TIEMPO_HASTA = "2027-12-31"
