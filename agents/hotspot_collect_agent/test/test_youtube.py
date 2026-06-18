"""
YouTube视频搜索抓取测试

使用 YouTube Data API v3 搜索视频，获取结构化数据。

⚠️ 重要说明：
YouTube搜索需要 YOUTUBE_API_KEY 才能获取数据。
请在 .env 文件中配置 YOUTUBE_API_KEY。
获取 API Key: https://console.cloud.google.com/apis/credentials

运行方式:
    conda activate ai-hotspot-monitor
    python -m agents.hotspot_collect_agent.test.test_youtube

    # 搜索其他关键词
    python -m agents.hotspot_collect_agent.test.test_youtube --keyword "关键词"

    # 按发布时间排序
    python -m agents.hotspot_collect_agent.test.test_youtube --order date

测试关键词: AI Agent
"""
import asyncio
import sys
import os
from datetime import datetime
from email.policy import default

# 确保项目根目录在路径中
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, project_root)

from agents.hotspot_collect_agent.youtube_auth.youtube_fetcher import YouTubeFetcher


# ==================== 测试函数 ====================
async def test_youtube_search(keyword: str = "AI Agent", order: str = "relevance", max_count: int = 20):
    """
    测试YouTube关键词视频搜索

    Args:
        keyword: 搜索关键词
        order: 排序方式 (relevance/date/rating/viewCount)
        max_count: 最大获取数量
    """
    print("\n" + "=" * 60)
    print("YouTube 关键词视频搜索测试")
    print("=" * 60)
    print(f"关键词: {keyword}")
    print(f"排序方式: {order}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 创建搜索器
    fetcher = YouTubeFetcher()

    # 检查API Key
    if not fetcher.available:
        print("\n❌ YOUTUBE_API_KEY 未配置，请检查 .env 文件")
        print("   在 .env 中添加: YOUTUBE_API_KEY=your_api_key")
        print("\n获取 API Key 方法:")
        print("   1. 访问 https://console.cloud.google.com/")
        print("   2. 启用 YouTube Data API v3")
        print("   3. 创建凭据获取 API Key")
        return []

    print(f"\n✓ API Key 已加载 (长度: {len(fetcher.api_key)} 字符)")

    # 发送搜索请求
    print(f"\n[步骤 1] 发送搜索请求 (关键词: {keyword})...")
    results = await fetcher.search(keyword, max_count=max_count, order=order)

    if results:
        print(f"\n✅ 成功获取: {len(results)} 条视频数据")

        # 显示前5条结果
        print("\n搜索结果:")
        print("-" * 40)
        for i, item in enumerate(results[:5], 1):
            title = item.get("title", "")[:50]
            author = item.get("author", {}).get("name", "")
            views = item.get("viewCount", 0)
            likes = item.get("likeCount", 0)
            comments = item.get("commentCount", 0)
            duration = item.get("duration", 0)
            mins, secs = divmod(duration, 60)
            url = item.get("url", "")
            published = item.get("publishedAt", "")[:10]

            print(f"\n[{i}] {title}")
            print(f"    频道: {author}")
            print(f"    播放: {views:,} | 点赞: {likes:,} | 评论: {comments:,}")
            print(f"    时长: {mins}:{secs:02d} | 发布: {published}")
            print(f"    URL: {url}")

        # 数据结构验证
        print("\n" + "-" * 40)
        print("数据结构验证:")
        required_fields = ["video_id", "title", "url"]
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

        # 统计信息汇总
        print("\n" + "-" * 40)
        print("统计汇总:")
        total_views = sum(r.get("viewCount", 0) for r in results)
        total_likes = sum(r.get("likeCount", 0) for r in results)
        avg_duration = sum(r.get("duration", 0) for r in results) / max(len(results), 1)
        print(f"  总播放量: {total_views:,}")
        print(f"  总点赞数: {total_likes:,}")
        print(f"  平均时长: {int(avg_duration // 60)}:{int(avg_duration % 60):02d}")

    else:
        print("\n❌ 未获取到视频数据")
        print("可能原因:")
        print("  1. API Key 无效或已过期")
        print("  2. YouTube Data API v3 未启用")
        print("  3. 搜索关键词无匹配结果")
        print("  4. API 配额已用完")

    print("\n" + "=" * 60)
    print(f"测试完成: {len(results)} 条结果")
    print("=" * 60)

    return results


async def test_youtube_with_search_result_format(keyword: str = "AI Agent"):
    """
    测试 YouTube 采集结果转换为 SearchResult 格式

    验证 YouTubeFetcher 的输出能否正确映射为工作流的 SearchResult 结构
    """
    print("\n" + "=" * 60)
    print("YouTube SearchResult 格式转换测试")
    print("=" * 60)

    fetcher = YouTubeFetcher()

    if not fetcher.available:
        print("\n❌ YOUTUBE_API_KEY 未配置")
        return False

    raw_results = await fetcher.search(keyword, max_count=10)
    if not raw_results:
        print("❌ 未获取到原始数据")
        return False

    # 模拟 SearchResult 格式转换（与 tools.py 中 fetch_douyin 逻辑一致）
    from datetime import datetime as dt

    search_results = []
    for video in raw_results:
        author_info = video.get("author", {})
        author = None
        if author_info:
            author = {
                "name": author_info.get("name", ""),
                "username": author_info.get("username", ""),
            }

        # 发布时间转换
        published_at = None
        pub_time = video.get("publishedAt", "")
        if pub_time:
            try:
                # YouTube 返回 ISO 8601 格式
                published_at = pub_time
            except Exception:
                pass

        search_result = {
            "title": video.get("title", ""),
            "content": video.get("desc", ""),
            "url": video.get("url", ""),
            "source": "youtube",
            "sourceId": video.get("video_id", ""),
            "publishedAt": published_at,
            "viewCount": video.get("viewCount", 0),
            "likeCount": video.get("likeCount", 0),
            "commentCount": video.get("commentCount", 0),
            "author": author,
        }
        search_results.append(search_result)

    # 验证转换结果
    print(f"\n转换结果: {len(search_results)} 条")

    valid_count = 0
    for i, sr in enumerate(search_results[:5], 1):
        has_title = bool(sr.get("title"))
        has_url = bool(sr.get("url"))
        has_source = sr.get("source") == "youtube"
        is_valid = has_title and has_url and has_source

        status = "✓" if is_valid else "❌"
        print(f"  [{i}] {status} title={has_title}, url={has_url}, source={has_source}")
        if is_valid:
            valid_count += 1

    success = valid_count > 0
    if success:
        print(f"\n✅ 格式转换验证通过 ({valid_count}/{min(len(search_results), 5)} 条有效)")
    else:
        print("\n❌ 格式转换验证失败")

    print("=" * 60)
    return success


async def test_multiple_keywords():
    """测试多个关键词"""
    print("\n" + "=" * 60)
    print("多关键词测试")
    print("=" * 60)

    keywords = ["AI Agent", "LangChain", "Claude AI"]
    fetcher = YouTubeFetcher()

    if not fetcher.available:
        print("❌ YOUTUBE_API_KEY 未配置")
        return False

    summary = []
    for kw in keywords:
        print(f"\n>>> 搜索: {kw}")
        results = await fetcher.search(kw, max_count=5)
        count = len(results)
        summary.append({"keyword": kw, "count": count})
        print(f"    结果: {count} 条")
        await asyncio.sleep(1)

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

    parser = argparse.ArgumentParser(description="YouTube数据源测试")
    parser.add_argument("--keyword", "-k", default="codex", help="搜索关键词")
    parser.add_argument("--order", "-o", default="relevance",
                        choices=["relevance", "date", "rating", "viewCount"],
                        help="排序方式")
    parser.add_argument("--max", "-n", type=int, default=5,
                        help="最大获取数量 (默认20)")
    parser.add_argument("--multi", "-m", action="store_true", help="多关键词测试")
    parser.add_argument("--format", "-f", action="store_true",
                        help="测试 SearchResult 格式转换")
    args = parser.parse_args()

    if args.multi:
        success = asyncio.run(test_multiple_keywords())
    elif args.format:
        success = asyncio.run(test_youtube_with_search_result_format(args.keyword))
    else:
        results = asyncio.run(test_youtube_search(args.keyword, args.order, max_count=args.max))
        success = len(results) > 0

    print("\n" + "=" * 60)
    if success:
        print("🎉 测试通过！可以进行后续开发")
    else:
        print("❌ 测试未通过，请检查 API Key 配置")
    print("=" * 60)

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
