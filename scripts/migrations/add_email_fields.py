"""
数据库迁移脚本：新增 hotspots 表字段
新增 emailSent 和 emailSentAt 字段

运行方式：
    conda activate ai-hotspot-monitor
    python scripts/migrations/add_email_fields.py
"""
import asyncio
from sqlalchemy import text
from backend.common.mysql import async_engine
from backend.common.logger import logger


async def migrate():
    """执行迁移"""
    logger.info("开始迁移：新增 emailSent 和 emailSentAt 字段...")

    async with async_engine.begin() as conn:
        # 检查字段是否已存在
        result = await conn.execute(
            text("SHOW COLUMNS FROM hotspots LIKE 'emailSent'")
        )
        if result.fetchone() is None:
            await conn.execute(
                text(
                    "ALTER TABLE hotspots ADD COLUMN emailSent BOOLEAN DEFAULT FALSE "
                    "COMMENT '是否已邮件通知'"
                )
            )
            logger.info("字段 emailSent 已添加")
        else:
            logger.info("字段 emailSent 已存在，跳过")

        result = await conn.execute(
            text("SHOW COLUMNS FROM hotspots LIKE 'emailSentAt'")
        )
        if result.fetchone() is None:
            await conn.execute(
                text(
                    "ALTER TABLE hotspots ADD COLUMN emailSentAt DATETIME NULL "
                    "COMMENT '邮件发送时间'"
                )
            )
            logger.info("字段 emailSentAt 已添加")
        else:
            logger.info("字段 emailSentAt 已存在，跳过")

    logger.info("迁移完成！")


if __name__ == "__main__":
    asyncio.run(migrate())