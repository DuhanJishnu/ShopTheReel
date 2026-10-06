"""Pytest fixtures: SQLite in-memory DB + FakeStore, override app deps.

CI also runs against Postgres/Redis service containers via DATABASE_URL_TEST;
locally defaults to SQLite so `make test` is green without `make up`.
"""

import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.clients.storage import FakeStore
from app.core.deps import set_store
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app

TEST_DB_URL = os.environ.get("DATABASE_URL_TEST", "sqlite+aiosqlite:///:memory:")


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
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
