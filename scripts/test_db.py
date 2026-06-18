import asyncio
import uuid

from sqlalchemy import text
from backend.common.mysql import async_engine, AsyncSessionLocal, init_db
from backend.models import Hotspot, Keyword
from backend.common.logger import logger


async def test_database():
    """测试数据库连接和操作"""

    # 1. 初始化数据库表
    logger.info("步骤 1: 初始化数据库表...")
    await init_db()
    logger.info("数据表创建完成")

    # 2. 插入测试数据
    logger.info("步骤 2: 插入测试数据...")
    async with AsyncSessionLocal() as session:
        # 插入关键词测试数据
        keyword1 = Keyword(
            id=str(uuid.uuid4()),
            keyword="AI",
            isActive=True
        )
        keyword2 = Keyword(
            id=str(uuid.uuid4()),
            keyword="GPT",
            isActive=True
        )
        session.add(keyword1)
        session.add(keyword2)
        await session.commit()
        await session.refresh(keyword1)
        await session.refresh(keyword2)
        logger.info(f"关键词插入成功: {keyword1.keyword}, {keyword2.keyword}")

        # 插入热点测试数据
        hotspot1 = Hotspot(
            id=str(uuid.uuid4()),
            title="OpenAI 发布 GPT-5 新功能",
            content="OpenAI 今天宣布 GPT-5 新版本，支持多模态处理和更长的上下文窗口...",
            url="https://twitter.com/openai/status/123456",
            source="twitter",
            sourceId="123456",
            isReal=True,
            relevance=95,
            relevanceReason="内容直接讨论 AI 和 GPT，高度相关",
            keywordMentioned=True,
            importance="high",
            summary="OpenAI 发布 GPT-5，支持多模态和长上下文",
            likeCount=5000,
            retweetCount=1200,
            authorName="OpenAI",
            authorUsername="openai",
            authorVerified=True,
            keywordId=keyword1.id
        )

        hotspot2 = Hotspot(
            id=str(uuid.uuid4()),
            title="Google DeepMind 最新研究成果",
            content="Google DeepMind 在 AI 领域取得突破性进展，新的 AlphaFold 版本...",
            url="https://news.google.com/articles/abc123",
            source="google",
            sourceId="abc123",
            isReal=True,
            relevance=80,
            relevanceReason="内容讨论 AI 研究进展，较为相关",
            keywordMentioned=True,
            importance="medium",
            summary="Google DeepMind AI 研究新突破",
            viewCount=10000,
            authorName="Google DeepMind",
            authorUsername="DeepMind",
            keywordId=keyword2.id
        )
        session.add(hotspot1)
        session.add(hotspot2)
        await session.commit()
        await session.refresh(hotspot1)
        await session.refresh(hotspot2)
        logger.info(f"热点插入成功: {hotspot1.title[:20]}..., {hotspot2.title[:20]}...")

    # 3. 查询验证数据
    logger.info("步骤 3: 查询验证数据...")
    async with AsyncSessionLocal() as session:
        # 查询关键词
        result = await session.execute(text("SELECT * FROM keywords"))
        keywords = result.fetchall()
        logger.info(f"关键词查询结果: {len(keywords)} 条")
        for kw in keywords:
            print(f"  - Keyword: id={kw[0]}, keyword={kw[1]}, isActive={kw[2]}")

        # 查询热点
        result = await session.execute(text("SELECT id, title, source, importance FROM hotspots"))
        hotspots = result.fetchall()
        logger.info(f"热点查询结果: {len(hotspots)} 条")
        for hs in hotspots:
            print(f"  - Hotspot: id={hs[0][:8]}..., title={hs[1][:30]}..., source={hs[2]}, importance={hs[3]}")

    # 4. 关闭连接
    await async_engine.dispose()
    logger.info("✅ 数据库连接测试完成，一切正常!")


if __name__ == "__main__":
    asyncio.run(test_database())