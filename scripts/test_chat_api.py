"""
测试热点问答聊天API
"""
import asyncio
import sys
sys.path.insert(0, '/Users/zigen/Desktop/ai-hotspot-monitor')

from backend.common.mysql import AsyncSessionLocal
from backend.models.hotspot import Hotspot
from backend.services.chat import process_chat
from sqlalchemy import select


async def test_chat():
    """测试聊天功能"""
    async with AsyncSessionLocal() as db:
        # 获取一个热点进行测试
        result = await db.execute(select(Hotspot).limit(1))
        hotspot = result.scalar_one_or_none()

        if not hotspot:
            print("没有找到热点数据，请先运行采集")
            return

        print(f"测试热点: {hotspot.title[:50]}...")
        print(f"热点ID: {hotspot.id}")
        print()

        # 测试发送消息
        message = "请简要介绍这条热点的主要内容"
        print(f"用户消息: {message}")
        print()

        try:
            reply, session_id, loaded_hotspots = await process_chat(
                db=db,
                hotspot_id=hotspot.id,
                message=message,
            )

            print(f"AI回复: {reply[:200]}...")
            print(f"会话ID: {session_id}")
            print(f"加载的热点: {loaded_hotspots}")
            print()
            print("测试成功!")

        except Exception as e:
            print(f"测试失败: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_chat())