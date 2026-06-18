"""
迁移脚本：创建 app_settings 表
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlalchemy import text
from backend.common.mysql import async_engine
from backend.common.logger import logger


async def migrate():
    async with async_engine.begin() as conn:
        # 检查表是否已存在
        result = await conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'app_settings'"
        ))
        exists = result.scalar() > 0

        if exists:
            logger.info("app_settings 表已存在，跳过创建")
            return

        await conn.execute(text("""
            CREATE TABLE app_settings (
                id VARCHAR(36) PRIMARY KEY,
                llm_base_url VARCHAR(500) NULL COMMENT 'LLM Base URL',
                llm_api_key VARCHAR(500) NULL COMMENT 'LLM API Key (加密)',
                llm_model_name VARCHAR(100) NULL COMMENT 'LLM 模型名称',
                llm_tested BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'LLM 是否测试通过',
                notify_email VARCHAR(200) NULL COMMENT '通知邮箱',
                twitter_api_key VARCHAR(500) NULL COMMENT 'Twitter API Key (加密)',
                twitter_tested BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Twitter API 是否测试通过',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """))

        logger.info("app_settings 表创建成功")


if __name__ == "__main__":
    asyncio.run(migrate())
