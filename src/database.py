from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import settings

db_url_str = str(settings.DATABASE_URL)
if db_url_str.startswith("postgres://"):
    db_url_str = db_url_str.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url_str.startswith("postgresql://"):
    db_url_str = db_url_str.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create async engine
engine = create_async_engine(
    db_url_str,
    echo=settings.LOG_LEVEL == "DEBUG",
    future=True
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
