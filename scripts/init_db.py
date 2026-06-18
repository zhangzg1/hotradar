import asyncio

from backend.common.mysql import init_db, async_engine
from backend.common.logger import logger


async def main():
    """初始化数据库"""
    logger.info("开始初始化数据库...")
    await init_db()
    await async_engine.dispose()
    logger.info("数据库初始化完成!")


if __name__ == "__main__":
    asyncio.run(main())