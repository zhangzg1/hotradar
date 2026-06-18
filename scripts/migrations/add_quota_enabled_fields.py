"""
数据库迁移脚本：fetch_quota_config 表添加 6 个 enabled 字段

运行方式：
    conda activate ai-hotspot-monitor
    python scripts/migrations/add_quota_enabled_fields.py
"""
import asyncio
from sqlalchemy import text
from backend.common.mysql import async_engine
from backend.common.logger import logger


COLUMNS = [
    ("twitter_enabled", "BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Twitter 是否启用'"),
    ("youtube_enabled", "BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'YouTube 是否启用'"),
    ("bilibili_enabled", "BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Bilibili 是否启用'"),
    ("douyin_enabled", "BOOLEAN NOT NULL DEFAULT TRUE COMMENT '抖音 是否启用'"),
    ("bing_enabled", "BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Bing 是否启用'"),
    ("sogou_enabled", "BOOLEAN NOT NULL DEFAULT TRUE COMMENT '搜狗 是否启用'"),
]


async def migrate():
    """执行迁移"""
    logger.info("开始迁移：fetch_quota_config 表添加 enabled 字段...")

    async with async_engine.begin() as conn:
        for col_name, col_def in COLUMNS:
            result = await conn.execute(
                text(f"SHOW COLUMNS FROM fetch_quota_config LIKE '{col_name}'")
            )
            if result.fetchone() is None:
                await conn.execute(
                    text(f"ALTER TABLE fetch_quota_config ADD COLUMN {col_name} {col_def}")
                )
                logger.info(f"  已添加列: {col_name}")
            else:
                logger.info(f"  列已存在，跳过: {col_name}")

    logger.info("迁移完成！")


if __name__ == "__main__":
    asyncio.run(migrate())
