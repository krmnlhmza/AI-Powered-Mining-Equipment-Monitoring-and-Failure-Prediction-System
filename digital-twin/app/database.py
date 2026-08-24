"""
PostgreSQL / TimescaleDB Bağlantısı
------------------------------------
Async SQLAlchemy engine + session factory. .env'de tanımlı POSTGRES_*
değişkenleriyle bağlanır; yoksa varsayılanlarla localhost:5432 (docker-compose).

  Base                — tüm ORM modellerinin temel sınıfı
  AsyncSessionLocal   — async DB oturumu üreticisi
  get_db()            — FastAPI Depends için bağımlılık (yield'li context)
  init_db()           — tabloları oluşturur (uygulama başlatma)
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = (
    f"postgresql+asyncpg://{os.getenv('POSTGRES_USER', 'postgres')}:"
    f"{os.getenv('POSTGRES_PASSWORD', 'postgres')}@"
    f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
    f"{os.getenv('POSTGRES_PORT', '5432')}/"
    f"{os.getenv('POSTGRES_DB', 'digital_twin')}"
)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
