from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import async_sessionmaker
from backend.core.config.development_config import get_config
from backend.common.logger import logger

config = get_config()

engine = create_engine(
    config.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=config.DEBUG,
)

async_engine = create_async_engine(
    config.ASYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=config.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


def get_db():
    """同步数据库会话依赖"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    """异步数据库会话依赖"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """初始化数据库，创建所有表"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表初始化完成")


async def close_db():
    """关闭数据库连接"""
    await async_engine.dispose()
    logger.info("数据库连接已关闭")