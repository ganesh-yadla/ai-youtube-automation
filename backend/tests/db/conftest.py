"""Shared fixtures for tests requiring a real Postgres (pytest.mark.db)."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings


@pytest.fixture
async def db_session():
    """A dedicated engine per test, bound to that test's event loop.

    Reusing app.infrastructure.db.session's module-level engine singleton
    here would break: pytest-asyncio gives each test function a fresh event
    loop, but a module-level engine's connection pool is bound to whichever
    loop first touched it, so later tests fail with "Event loop is closed".
    """
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session
        # Tests that intentionally trigger a DB error (e.g. a uniqueness
        # violation) leave the session's transaction rolled back server-side
        # but not reset client-side - rollback() first or the cleanup query
        # itself raises PendingRollbackError instead of running.
        await session.rollback()
        await session.execute(text("TRUNCATE trend_searches CASCADE"))
        await session.commit()

    await engine.dispose()
