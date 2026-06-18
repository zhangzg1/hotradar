"""
数据库迁移脚本：热点问答功能数据表

新增字段：
- hotspots 表新增 fullContent 字段

新增表：
- chat_sessions 表：聊天会话
- chat_messages 表：聊天消息

运行方式：
    conda activate ai-hotspot-monitor
    python scripts/migrations/add_chat_tables.py
"""
import asyncio
from sqlalchemy import text
from backend.common.mysql import async_engine
from backend.common.logger import logger


async def migrate():
    """执行迁移"""
    logger.info("开始迁移：热点问答功能数据表...")

    async with async_engine.begin() as conn:
        # ==================== 1. hotspots 表新增 fullContent 字段 ====================
        result = await conn.execute(
            text("SHOW COLUMNS FROM hotspots LIKE 'fullContent'")
        )
        if result.fetchone() is None:
            await conn.execute(
                text(
                    "ALTER TABLE hotspots ADD COLUMN fullContent TEXT NULL "
                    "COMMENT '完整原文内容（含字幕）' AFTER content"
                )
            )
            logger.info("字段 fullContent 已添加")

            # 为现有热点补充 fullContent（从 content 字段复制，排除 B站）
            await conn.execute(
                text(
                    "UPDATE hotspots SET fullContent = content WHERE source != 'bilibili' AND fullContent IS NULL"
                )
            )
            logger.info("现有热点 fullContent 已补充")
        else:
            logger.info("字段 fullContent 已存在，跳过")

        # ==================== 2. 创建 chat_sessions 表 ====================
        result = await conn.execute(
            text("SHOW TABLES LIKE 'chat_sessions'")
        )
        if result.fetchone() is None:
            await conn.execute(
                text("""
                    CREATE TABLE chat_sessions (
                        id VARCHAR(36) PRIMARY KEY,
                        hotspotId VARCHAR(36) NOT NULL,
                        createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (hotspotId) REFERENCES hotspots(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
            )
            logger.info("表 chat_sessions 已创建")
        else:
            logger.info("表 chat_sessions 已存在，跳过")

        # ==================== 3. 创建 chat_messages 表 ====================
        result = await conn.execute(
            text("SHOW TABLES LIKE 'chat_messages'")
        )
        if result.fetchone() is None:
            await conn.execute(
                text("""
                    CREATE TABLE chat_messages (
                        id VARCHAR(36) PRIMARY KEY,
                        sessionId VARCHAR(36) NOT NULL,
                        role VARCHAR(20) NOT NULL,
                        content TEXT NOT NULL,
                        loadedHotspots TEXT NULL,
                        createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (sessionId) REFERENCES chat_sessions(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
            )
            logger.info("表 chat_messages 已创建")
        else:
            logger.info("表 chat_messages 已存在，跳过")

    logger.info("迁移完成！")


if __name__ == "__main__":
    asyncio.run(migrate())