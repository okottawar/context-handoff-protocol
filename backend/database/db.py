"""
database/db.py

Async SQLAlchemy engine, session factory, and startup helpers.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.config import settings
from backend.database.models import Base

# For SQLite we need check_same_thread=False and a StaticPool so the same
# connection can be used across threads during tests / dev.
_connect_args = {}
_pool_kwargs: dict = {}

if "sqlite" in settings.database_url:
    _connect_args = {"check_same_thread": False}
    _pool_kwargs  = {"poolclass": StaticPool}

engine = create_async_engine(
    settings.database_url,
    connect_args=_connect_args,
    echo=False,
    **_pool_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db() -> None:
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        yield session
