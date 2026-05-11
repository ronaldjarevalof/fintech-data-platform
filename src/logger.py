"""Logging estructurado: cada mensaje incluye run_id para trazabilidad."""

import logging
import sys

import structlog

from src.config import LOG_LEVEL


def configure_logging() -> None:
    """Configura structlog con salida JSON y nivel desde variable de entorno."""
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def get_logger(run_id: str) -> structlog.stdlib.BoundLogger:
    """Retorna un logger con run_id vinculado a todos los mensajes.

    Args:
        run_id: UUID de la ejecución actual del pipeline.

    Returns:
        Logger structlog con run_id en el contexto.
    """
    configure_logging()
    return structlog.get_logger().bind(run_id=run_id)
