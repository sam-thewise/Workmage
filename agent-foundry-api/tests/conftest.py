"""Pytest configuration and fixtures for API tests."""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.db.base import async_engine
from app.db.session import get_db
from app.main import app
from app.models.agent import Agent
from app.models.agent_wallet import AgentWallet
from app.models.user import User, UserRole


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Session with rollback so no data persists. Requires running Postgres (DATABASE_URL)."""
    try:
        conn = await async_engine.connect()
    except Exception as e:
        pytest.skip(f"Database not available: {e}")
    try:
        await conn.begin()
        async with AsyncSession(bind=conn, expire_on_commit=False, autoflush=False) as session:
            yield session
    finally:
        await conn.rollback()
        await conn.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        email="expert@test.example",
        hashed_password=get_password_hash("testpass123"),
        role=UserRole.EXPERT,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def test_admin(db_session: AsyncSession) -> User:
    user = User(
        email="admin@test.example",
        hashed_password=get_password_hash("adminpass123"),
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict[str, str]:
    token = create_access_token(subject=str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_headers(test_admin: User) -> dict[str, str]:
    token = create_access_token(subject=str(test_admin.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def test_agent(db_session: AsyncSession, test_user: User) -> Agent:
    agent = Agent(
        expert_id=test_user.id,
        name="Test Agent",
        description="For tests",
        manifest={
            "name": "Test Agent",
            "version": "1.0",
            "schema_version": "1.0",
            "description": "Test",
            "authors": [],
            "created_at": "2025-01-01T00:00:00Z",
            "skills": [],
            "modules": [],
        },
        status="listed",
        approval_status="approved",
    )
    db_session.add(agent)
    await db_session.flush()
    return agent


@pytest_asyncio.fixture
async def test_wallet(db_session: AsyncSession, test_user: User, test_agent: Agent) -> AgentWallet:
    wallet = AgentWallet(
        agent_id=test_agent.id,
        owner_user_id=test_user.id,
        network="avalanche",
        chain_id=43114,
        wallet_address="0x1111111111111111111111111111111111111111",
        status="active",
    )
    db_session.add(wallet)
    await db_session.flush()
    return wallet
