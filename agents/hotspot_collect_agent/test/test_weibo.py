"""
微博数据抓取测试脚本

使用"勇士"关键词测试微博热搜抓取

运行方式:
    conda activate ai-hotspot-monitor
    python -m agents.hotspot_collect_agent.test.test_weibo
"""
import asyncio
import sys
import os

# 确保项目根目录在路径中
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from backend.common.logger import logger
from agents.hotspot_collect_agent.tools import fetch_weibo


async def test_weibo(keyword: str = "勇士"):
    """
    测试微博数据抓取

    Args:
        keyword: 测试关键词
    """
    print("\n" + "="*60)
    print("微博数据抓取测试")
    print("="*60)
    print(f"关键词: {keyword}")
    print("="*60 + "\n")

    try:
        results = await fetch_weibo(keyword, {})

        if len(results) > 0:
            print(f"✅ 成功抓取: {len(results)} 条结果\n")

            print("抓取结果详情:")
            print("-"*40)

            for i, item in enumerate(results, 1):
                title = item.get("title", "")
                content = item.get("content", "")
                url = item.get("url", "")
                view_count = item.get("viewCount", 0)

                print(f"\n[{i}] {title}")
                print(f"    内容: {content}")
                print(f"    热度: {view_count}")
                print(f"    URL: {url}")

        else:
            print("⚠️  抓取成功但无匹配结果\n")
            print("说明: 微博抓取的是实时热搜榜，只能匹配恰好上榜的热词")
            print("如果热搜榜中没有包含关键词的话题，则返回空结果")

    except Exception as e:
        print(f"❌ 抓取失败: {e}")

    print("\n" + "="*60)
    print("测试完成")
    print("="*60 + "\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="测试微博数据抓取")
    parser.add_argument("--keyword", type=str, default="勇士", help="搜索关键词")
    args = parser.parse_args()

    asyncio.run(test_weibo(args.keyword))