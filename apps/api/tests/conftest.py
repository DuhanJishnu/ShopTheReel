"""Pytest fixtures: Postgres when DATABASE_URL_TEST is set, else SQLite + FakeStore.

Vector columns compile to pgvector on Postgres and JSON on SQLite (see
EmbeddingVector), so all tests run anywhere; ANN retrieval tests are marked
needs_pg and only run against Postgres (compose locally, service in CI).
"""

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.clients.storage import FakeStore
from app.core.deps import set_store
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app

TEST_DB_URL = os.environ.get("DATABASE_URL_TEST", "sqlite+aiosqlite:///:memory:")
needs_pg = pytest.mark.skipif(not os.environ.get("DATABASE_URL_TEST"), reason="needs Postgres (DATABASE_URL_TEST)")


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    if engine.dialect.name == "postgresql":
        async with engine.begin() as conn:
            tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
            await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    app = create_app()
    set_store(FakeStore())

    async def _override():  # type: ignore[no-untyped-def]
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
