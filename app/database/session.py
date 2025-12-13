from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.core.config import settings
from loguru import logger


# -------------------------------------------
# ASYNC ENGINE
# -------------------------------------------
engine = create_async_engine(
    settings.DATABASE_URL,         # Must be async driver e.g. postgres+asyncpg
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False
)

# -------------------------------------------
# ASYNC SESSION MAKER
# -------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

# -------------------------------------------
# MODEL BASE
# -------------------------------------------
Base = declarative_base()


# -------------------------------------------
# SESSION DEPENDENCY
# -------------------------------------------
@asynccontextmanager
async def get_session() -> AsyncSession:
    session: AsyncSession = AsyncSessionLocal()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# -------------------------------------------
# INIT DB
# -------------------------------------------
async def init_db():
    """
    Run at startup: ensures DB is accessible 
    and discards cached execution plans.
    """
    try:
        async with engine.begin() as conn:
            # Optional: run table creation (not recommended in prod)
            # await conn.run_sync(Base.metadata.create_all)

            await conn.execute(text("SELECT 1"))
            logger.info("✓ Async database connected successfully")

            # If using PostgreSQL w/ PgBouncer:
            await conn.execute(text("DISCARD PLANS"))

        return True

    except Exception as e:
        logger.error(f"✗ Async database initialization failed: {str(e)}")
        return False
