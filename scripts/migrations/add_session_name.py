"""
迁移脚本：为 chat_sessions 表添加 name 字段

运行方式：
    conda activate ai-hotspot-monitor
    python scripts/migrations/add_session_name.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from backend.common.mysql import async_engine


async def migrate():
    """执行迁移"""
    async with async_engine.begin() as conn:
        # 检查字段是否存在
        result = await conn.execute(
            text("SHOW COLUMNS FROM chat_sessions LIKE 'name'")
        )
        exists = result.fetchone()

        if not exists:
            print("添加 name 字段到 chat_sessions 表...")
            await conn.execute(
                text("ALTER TABLE chat_sessions ADD COLUMN name VARCHAR(100) NULL COMMENT '会话名称'")
            )
            print("✅ 迁移完成")
        else:
            print("⚠️ name 字段已存在，无需迁移")


if __name__ == "__main__":
    asyncio.run(migrate())