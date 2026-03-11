"""Database base and session setup."""
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


sync_engine = create_engine(
    settings.DATABASE_SYNC_URL,
    pool_pre_ping=True,
    echo=False,
)

# asyncpg does not accept sslmode= in the URL; strip it and use connect_args ssl=True.
_async_url_str = settings.DATABASE_URL
_async_connect_args = {}
_parsed = urlparse(_async_url_str)
if _parsed.query:
    _params = parse_qs(_parsed.query, keep_blank_values=True)
    if "sslmode" in _params:
        _async_connect_args["ssl"] = True
        del _params["sslmode"]
        _new_query = urlencode(_params, doseq=True)
        _async_url_str = urlunparse((_parsed.scheme, _parsed.netloc, _parsed.path, _parsed.params, _new_query, _parsed.fragment))

async_engine = create_async_engine(
    _async_url_str,
    pool_pre_ping=True,
    echo=False,
    connect_args=_async_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)
