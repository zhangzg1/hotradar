"""
数据库迁移脚本：新增 scheduler_config 表

运行方式：
    conda activate ai-hotspot-monitor
    python scripts/migrations/add_scheduler_config.py
"""
import asyncio
from sqlalchemy import text
from backend.common.mysql import async_engine
from backend.common.logger import logger


async def migrate():
    """执行迁移"""
    logger.info("开始迁移：新增 scheduler_config 表...")

    async with async_engine.begin() as conn:
        result = await conn.execute(
            text("SHOW TABLES LIKE 'scheduler_config'")
        )
        if result.fetchone() is None:
            await conn.execute(
                text("""
                    CREATE TABLE scheduler_config (
                        id VARCHAR(36) PRIMARY KEY COMMENT '配置ID',
                        interval_hours INT NOT NULL DEFAULT 2 COMMENT '调度间隔（小时）',
                        is_enabled BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否启用',
                        last_run_at DATETIME NULL COMMENT '上次执行时间',
                        last_run_status VARCHAR(20) NULL COMMENT '上次执行状态: success/failed/skipped',
                        next_run_at DATETIME NULL COMMENT '下次执行时间',
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='定时调度配置'
                """)
            )
            # 插入默认配置行
            import uuid
            await conn.execute(
                text(
                    "INSERT INTO scheduler_config (id, interval_hours, is_enabled) "
                    "VALUES (:id, 2, FALSE)"
                ),
                {"id": str(uuid.uuid4())}
            )
            logger.info("scheduler_config 表已创建并插入默认配置")
        else:
            logger.info("scheduler_config 表已存在，跳过")

    logger.info("迁移完成！")


if __name__ == "__main__":
    asyncio.run(migrate())
