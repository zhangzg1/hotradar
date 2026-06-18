"""
抖音视频搜索抓取测试（纯HTTP方案）

使用纯HTTP请求搜索抖音视频，无需Playwright或签名JS文件。
搜索API不需要a-bogus签名验证。

⚠️ 重要说明：
抖音搜索需要登录cookie才能获取数据。
首次使用需要运行 douyin_auth/get_douyin_cookie.py 获取cookie。

运行方式:
    # 确保cookie文件存在
    conda activate ai-hotspot-monitor
    python -m agents.hotspot_collect_agent.test.test_douyin

    # 搜索其他关键词
    python -m agents.hotspot_collect_agent.test.test_douyin --keyword "关键词"

测试关键词: 剑来
"""
import asyncio
import sys
import os
from datetime import datetime

# 确保项目根目录在路径中
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from agents.hotspot_collect_agent.douyin_auth.douyin_fetcher import DouyinFetcher, load_cookie_from_file


# ==================== 测试函数 ====================
async def test_douyin_search(keyword: str = "剑来"):
    """
    测试抖音关键词视频搜索（纯HTTP方案）
    """
    print("\n" + "=" * 60)
    print("抖音关键词视频搜索测试")
    print("=" * 60)
    print(f"关键词: {keyword}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 创建搜索器
    fetcher = DouyinFetcher()

    # 检查cookie
    if not fetcher.cookie:
        print("\n❌ Cookie未加载，请检查douyin_cookie.json文件")
        print(f"   期望路径: {fetcher.COOKIE_FILE}")
        print("\n获取Cookie方法:")
        print("   cd douyin_cralwer && python get_douyin_cookie.py")
        return []

    print(f"\n✓ Cookie已加载 (长度: {len(fetcher.cookie)} 字符)")
    print(f"✓ msToken: {fetcher.ms_token[:30] if fetcher.ms_token else '无'}...")

    print("\n[步骤 1] 发送HTTP请求搜索...")
    results = await fetcher.search(keyword, max_count=20)

    if results:
        print(f"\n✅ 成功获取: {len(results)} 条视频数据")
        print("\n搜索结果:")
        print("-" * 40)
        for i, item in enumerate(results[:5], 1):
            title = item.get("title", "")
            url = item.get("url", "")
            author = item.get("author", {}).get("name", "")
            likes = item.get("likeCount", 0)
            comments = item.get("commentCount", 0)
            print(f"\n[{i}] {title[:50]}...")
            print(f"    作者: {author}")
            print(f"    点赞: {likes} | 评论: {comments}")
            print(f"    URL: {url}")

        # 验证数据结构
        print("\n" + "-" * 40)
        print("数据结构验证:")
        required_fields = ["aweme_id", "title", "url"]
        all_valid = True

        for i, item in enumerate(results[:5], 1):
            missing = [f for f in required_fields if not item.get(f)]
            if missing:
                print(f"  [{i}] ❌ 缺少字段: {missing}")
                all_valid = False
            else:
                print(f"  [{i}] ✓ 数据结构完整")

        if all_valid:
            print("\n✅ 所有数据结构验证通过")
    else:
        print("\n❌ 未获取到视频数据")
        print("可能原因:")
        print("  1. Cookie已过期，需要重新获取")
        print("  2. 搜索关键词无匹配结果")
        print("  3. 触发了验证检查")

    print("\n" + "=" * 60)
    print(f"测试完成: {len(results)} 条结果")
    print("=" * 60)

    return results


async def test_multiple_keywords():
    """测试多个关键词"""
    print("\n" + "=" * 60)
    print("多关键词测试")
    print("=" * 60)

    keywords = ["剑来", "AI", "人工智能"]
    fetcher = DouyinFetcher()

    if not fetcher.cookie:
        print("❌ Cookie未加载")
        return False

    summary = []
    for kw in keywords:
        print(f"\n>>> 搜索: {kw}")
        results = await fetcher.search(kw, max_count=5)
        count = len(results)
        summary.append({"keyword": kw, "count": count})
        print(f"    结果: {count} 条")
        await asyncio.sleep(2)

    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    total = sum(s["count"] for s in summary)
    print(f"总结果数: {total}")
    for s in summary:
        print(f"  - {s['keyword']}: {s['count']} 条")

    return total > 0


# ==================== 主入口 ====================
def main():
    """主入口"""
    import argparse
    parser = argparse.ArgumentParser(description="抖音数据源测试")
    parser.add_argument("--keyword", "-k", default="剑来", help="搜索关键词")
    parser.add_argument("--multi", "-m", action="store_true", help="多关键词测试")
    args = parser.parse_args()

    if args.multi:
        success = asyncio.run(test_multiple_keywords())
    else:
        results = asyncio.run(test_douyin_search(args.keyword))
        success = len(results) > 0

    print("\n" + "=" * 60)
    if success:
        print("🎉 测试通过！可以进行后续开发")
    else:
        print("❌ 测试未通过，请检查Cookie")
    print("=" * 60)

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)