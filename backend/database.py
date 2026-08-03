"""
Database connection and session management.

Connection settings come from config.py — nothing host-specific lives here.
"""

import asyncio
import logging
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from config import (
    DATABASE_URL,
    DB_COMMAND_TIMEOUT,
    DB_CONNECT_TIMEOUT,
    DB_INIT_TIMEOUT,
)
from models import Base

logger = logging.getLogger(__name__)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,      # drop dead connections instead of handing them out
    pool_recycle=1800,       # hosted Postgres often closes idle connections
    connect_args={
        "timeout": DB_CONNECT_TIMEOUT,
        "command_timeout": DB_COMMAND_TIMEOUT,
    },
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Set by init_db(); read by /health. False means the app is up but DB-backed
# routes will return 503 until the database comes back.
db_ready = False


async def init_db() -> bool:
    """
    Create tables if needed.

    Never raises and never blocks past DB_INIT_TIMEOUT: an unreachable database
    must not stop the app from starting, or the entire service becomes
    unreachable — including /health — with no way to see what's wrong.
    """
    global db_ready
    started = time.monotonic()
    try:
        async with asyncio.timeout(DB_INIT_TIMEOUT):
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        db_ready = True
        logger.info("Database ready (%.1fs)", time.monotonic() - started)
    except TimeoutError:
        # Either the connect timeout or the overall init timeout — report the
        # elapsed time rather than a configured value, so the log says what
        # actually happened.
        db_ready = False
        logger.error(
            "Database unreachable after %.1fs — starting anyway; DB routes will 503",
            time.monotonic() - started,
        )
    except Exception as exc:
        db_ready = False
        logger.error(
            "Database init failed after %.1fs (%s: %s) — starting anyway",
            time.monotonic() - started, type(exc).__name__, exc,
        )
    return db_ready


async def check_db(timeout: float = 2.0) -> bool:
    """
    Live connectivity probe for /health.

    Bounded and non-throwing: reports what is true *now* rather than what was
    true at startup, but can never become the reason /health itself hangs.
    """
    try:
        async with asyncio.timeout(timeout):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
