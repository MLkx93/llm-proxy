"""
Idempotent schema creation. Call init_db() on app startup.

Never raises on connection failure — logs and continues so the demo degrades
gracefully if Postgres isn't running.
"""
from src.proxy.logging import get_logger
from .models import Base
from .session import get_engine

logger = get_logger("db")


async def init_db() -> bool:
    """Create tables if they don't exist. Returns True on success, False if DB unreachable."""
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("db_initialized")
        return True
    except Exception as exc:
        logger.error("db_init_failed", extra={"error": str(exc)})
        return False
