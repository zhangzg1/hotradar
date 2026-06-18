import asyncio
from sqlalchemy import text
from backend.common.mysql import AsyncSessionLocal, async_engine


async def test_sql():
    """执行 SQL 测试"""
    async with AsyncSessionLocal() as session:
        # 在这里修改你的 SQL 语句
        sql = "SELECT * FROM keywords"

        result = await session.execute(text(sql))
        rows = result.fetchall()

        print(f"查询结果: {len(rows)} 条")
        for row in rows:
            print(row)

    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_sql())