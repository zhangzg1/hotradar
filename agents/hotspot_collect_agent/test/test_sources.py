"""
数据源抓取独立测试

测试各数据源的抓取功能是否正常

运行方式:
    conda activate ai-hotspot-monitor
    python -m agents.hotspot_collect_agent.test.test_sources
"""
import asyncio
import sys
import os

# 确保项目根目录在路径中
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from backend.common.logger import logger
from agents.hotspot_collect_agent.tools import (
    fetch_twitter,
    fetch_bing,
    fetch_sogou,
    fetch_bilibili,
)


# ==================== 测试函数 ====================
async def test_single_source(source_name: str, fetch_func, keyword: str = "Hermes Agent"):
    """
    测试单个数据源

    Args:
        source_name: 数据源名称
        fetch_func: 抓取函数
        keyword: 测试关键词

    Returns:
        (是否成功, 抓取数量, 错误信息)
    """
    print(f"\n{'='*60}")
    print(f"测试数据源: {source_name}")
    print(f"关键词: {keyword}")
    print("="*60)

    try:
        results = await fetch_func(keyword, {})
        count = len(results)

        if count > 0:
            print(f"✅ 成功抓取: {count} 条结果")

            # 显示前3条结果
            print("\n前3条结果示例:")
            for i, item in enumerate(results[:3], 1):
                title = item.get("title", "")[:50]
                url = item.get("url", "")[:60]
                print(f"  [{i}] {title}...")
                print(f"      URL: {url}...")

            return (True, count, None)
        else:
            print("⚠️  抓取成功但返回0条结果")
            return (True, 0, "无结果")

    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        return (False, 0, str(e))


async def test_all_sources():
    """
    测试所有数据源
    """
    print("\n" + "="*60)
    print("数据源抓取全面测试")
    print("="*60)

    keyword = "Hermes Agent"

    sources = [
        ("Bing", fetch_bing),
        ("搜狗", fetch_sogou),
        ("Bilibili", fetch_bilibili),
    ]

    results_summary = []

    for source_name, fetch_func in sources:
        success, count, error = await test_single_source(source_name, fetch_func, keyword)
        results_summary.append({
            "source": source_name,
            "success": success,
            "count": count,
            "error": error,
        })

        # 添加间隔避免连续请求
        await asyncio.sleep(1)

    # 输出总结报告
    print("\n" + "="*60)
    print("测试总结报告")
    print("="*60)

    successful = [r for r in results_summary if r["success"] and r["count"] > 0]
    empty_results = [r for r in results_summary if r["success"] and r["count"] == 0]
    failed = [r for r in results_summary if not r["success"]]

    print("\n✅ 成功抓取数据的数据源:")
    for r in successful:
        print(f"  - {r['source']}: {r['count']} 条")

    print("\n⚠️  抓取成功但无结果的数据源:")
    for r in empty_results:
        reason = r['error'] or "未知原因"
        print(f"  - {r['source']}: {reason}")

    print("\n❌ 抓取失败的数据源:")
    for r in failed:
        print(f"  - {r['source']}: {r['error']}")

    print("\n" + "="*60)
    print(f"总计: {len(successful)} 个成功, {len(empty_results)} 个无结果, {len(failed)} 个失败")
    print("="*60 + "\n")

    return results_summary


# ==================== 主入口 ====================
if __name__ == "__main__":
    asyncio.run(test_all_sources())