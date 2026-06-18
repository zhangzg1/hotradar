"""
数据库迁移脚本：多用户支持

新增表：
- users 表：用户账号

新增字段：
- keywords / hotspots / chat_sessions / scheduler_config / fetch_quota_config / app_settings 表增加 user_id 字段

数据迁移：
- 所有现有数据关联到初始用户 zeric

索引变更：
- keywords 表 text 列的唯一索引改为 (text, user_id) 复合索引

运行方式：
    conda activate ai-hotspot-monitor
    python scripts/migrations/add_multi_user.py
"""
import asyncio
import uuid
from sqlalchemy import text
from backend.common.mysql import async_engine
from backend.common.logger import logger

# 初始用户信息
ZERIC_USERNAME = "zeric"
ZERIC_PASSWORD = "Gzhu.3012"
ZERIC_USER_ID = str(uuid.uuid4())


async def migrate():
    """执行迁移"""
    logger.info("开始迁移：多用户支持...")

    async with async_engine.begin() as conn:
        # ==================== 1. 创建 users 表 ====================
        result = await conn.execute(text("SHOW TABLES LIKE 'users'"))
        if result.fetchone() is None:
            await conn.execute(text("""
                CREATE TABLE users (
                    id VARCHAR(36) PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
                    hashed_password VARCHAR(200) NOT NULL COMMENT '密码哈希',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """))
            logger.info("表 users 已创建")
        else:
            logger.info("表 users 已存在，跳过")

        # ==================== 2. 插入初始用户 zeric ====================
        result = await conn.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": ZERIC_USERNAME}
        )
        existing_user = result.fetchone()
        if existing_user:
            # 用户已存在，获取其 ID
            global ZERIC_USER_ID
            ZERIC_USER_ID = existing_user[0]
            logger.info(f"用户 '{ZERIC_USERNAME}' 已存在 (ID: {ZERIC_USER_ID})")
        else:
            # 哈希密码
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            hashed = pwd_context.hash(ZERIC_PASSWORD)

            await conn.execute(text("""
                INSERT INTO users (id, username, hashed_password, created_at)
                VALUES (:id, :username, :hashed_password, NOW())
            """), {"id": ZERIC_USER_ID, "username": ZERIC_USERNAME, "hashed_password": hashed})
            logger.info(f"用户 '{ZERIC_USERNAME}' 已创建 (ID: {ZERIC_USER_ID})")

        # ==================== 3. 为各表增加 user_id 字段 ====================
        tables_to_add_user_id = [
            "keywords",
            "hotspots",
            "chat_sessions",
            "scheduler_config",
            "fetch_quota_config",
            "app_settings",
        ]

        for table_name in tables_to_add_user_id:
            result = await conn.execute(
                text(f"SHOW COLUMNS FROM {table_name} LIKE 'user_id'")
            )
            if result.fetchone() is None:
                await conn.execute(text(
                    f"ALTER TABLE {table_name} ADD COLUMN user_id VARCHAR(36) NULL "
                    f"COMMENT '用户 ID' AFTER id"
                ))
                logger.info(f"表 {table_name} 已添加 user_id 字段")
            else:
                logger.info(f"表 {table_name} 的 user_id 字段已存在，跳过")

        # ==================== 4. 迁移现有数据到 zeric 用户 ====================
        for table_name in tables_to_add_user_id:
            result = await conn.execute(
                text(f"SELECT COUNT(*) FROM {table_name} WHERE user_id IS NULL")
            )
            null_count = result.scalar()
            if null_count > 0:
                await conn.execute(
                    text(f"UPDATE {table_name} SET user_id = :user_id WHERE user_id IS NULL"),
                    {"user_id": ZERIC_USER_ID}
                )
                logger.info(f"表 {table_name}: {null_count} 条数据已关联到用户 {ZERIC_USERNAME}")
            else:
                logger.info(f"表 {table_name}: 无需迁移")

        # ==================== 5. 迁移 douyin_cookies 的 user_id ====================
        result = await conn.execute(
            text("SELECT COUNT(*) FROM douyin_cookies WHERE user_id = '1'")
        )
        old_user_count = result.scalar()
        if old_user_count > 0:
            await conn.execute(
                text("UPDATE douyin_cookies SET user_id = :user_id WHERE user_id = '1'"),
                {"user_id": ZERIC_USER_ID}
            )
            logger.info(f"表 douyin_cookies: {old_user_count} 条数据 user_id 已从 '1' 更新为 zeric 的 UUID")
        else:
            logger.info("表 douyin_cookies: 无需迁移")

        # ==================== 6. keywords 表唯一索引变更 ====================
        # 检查当前是否有 text 列的单列唯一索引
        result = await conn.execute(text("SHOW INDEX FROM keywords WHERE Column_name = 'text'"))
        indexes = result.fetchall()

        text_unique_index = None
        for idx in indexes:
            # MySQL SHOW INDEX 返回: Table, Non_unique, Key_name, Seq_in_index, Column_name, ...
            key_name = idx[2]
            non_unique = idx[1]
            if key_name != "PRIMARY" and non_unique == 0:
                text_unique_index = key_name
                break

        if text_unique_index:
            await conn.execute(text(f"ALTER TABLE keywords DROP INDEX `{text_unique_index}`"))
            logger.info(f"已删除 keywords 表的旧唯一索引: {text_unique_index}")
        else:
            logger.info("keywords 表无旧唯一索引需要删除")

        # 创建复合唯一索引
        result = await conn.execute(
            text("SHOW INDEX FROM keywords WHERE Key_name = 'uq_keyword_text_user'")
        )
        if result.fetchone() is None:
            await conn.execute(text(
                "ALTER TABLE keywords ADD UNIQUE INDEX uq_keyword_text_user (text, user_id)"
            ))
            logger.info("已创建 keywords 表的复合唯一索引: uq_keyword_text_user (text, user_id)")
        else:
            logger.info("keywords 表的复合唯一索引已存在，跳过")

    logger.info("多用户迁移完成！")


if __name__ == "__main__":
    asyncio.run(migrate())
