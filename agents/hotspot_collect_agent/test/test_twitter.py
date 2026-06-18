"""
Twitter 数据抓取测试脚本

测试 Twitter API 是否能够正确抓取数据

运行方式:
    conda activate ai-hotspot-monitor
    python -m agents.hotspot_collect_agent.test.test_twitter
"""
import asyncio
import aiohttp
import sys
import os
from datetime import datetime, timedelta
from urllib.parse import urlencode

# 确保项目根目录在路径中
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from backend.common.logger import logger


# ==================== API 配置 ====================
TWITTER_API_BASE = "https://api.twitterapi.io"
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY") or "new1_04f10d0072964f599359e32ff4d058cd"

# 质量过滤阈值
TWITTER_FILTER_CONFIG = {
    "minLikes": 10,
    "minRetweets": 5,
    "minViews": 500,
    "minFollowers": 100,
    "onlyOriginalTweets": True
}


# ==================== 辅助函数 ====================
def format_since_date(days_ago: int) -> str:
    """
    格式化日期为 Twitter 搜索格式 (YYYY-MM-DD)
    """
    date = datetime.now() - timedelta(days=days_ago)
    return date.strftime("%Y-%m-%d")


def build_advanced_query(keyword: str, search_type: str = "Top") -> str:
    """
    构建 Twitter 高级搜索查询字符串

    Args:
        keyword: 搜索关键词
        search_type: 搜索类型 (Top/Latest)

    Returns:
        查询字符串
    """
    parts = [keyword]

    # 排除转发和回复
    parts.append("-filter:retweets")
    parts.append("-filter:replies")

    # 时间范围
    days_ago = 7 if search_type == "Top" else 3
    parts.append(f"since:{format_since_date(days_ago)}")

    # Top 搜索额外条件
    if search_type == "Top":
        parts.append("min_faves:10")

    return " ".join(parts)


# ==================== API 请求 ====================
async def make_twitter_request(endpoint: str, params: dict) -> dict:
    """
    发送 Twitter API 请求

    Args:
        endpoint: API endpoint
        params: 请求参数

    Returns:
        API 响应数据
    """
    url = f"{TWITTER_API_BASE}{endpoint}?{urlencode(params)}"

    headers = {
        "X-API-Key": TWITTER_API_KEY,
        "Content-Type": "application/json",
    }

    print(f"\n请求 URL: {url}")
    print(f"请求参数: {params}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                print(f"响应状态码: {response.status}")

                if response.status != 200:
                    error_text = await response.text()
                    print(f"错误响应: {error_text[:500]}")
                    return {"error": f"HTTP {response.status}", "detail": error_text[:500]}

                data = await response.json()
                return data

    except asyncio.TimeoutError:
        return {"error": "请求超时 (30s)"}
    except aiohttp.ClientError as e:
        return {"error": f"网络错误: {e}"}
    except Exception as e:
        return {"error": f"未知错误: {e}"}


async def fetch_tweet_page(query: str, query_type: str, cursor: str = None) -> dict:
    """
    获取单页推文

    Args:
        query: 查询字符串
        query_type: 搜索类型 (Top/Latest)
        cursor: 分页游标

    Returns:
        推文数据和下一页游标
    """
    params = {
        "query": query,
        "queryType": query_type,
    }

    if cursor:
        params["cursor"] = cursor

    # 使用正确的 endpoint
    endpoint = "/twitter/tweet/advanced_search"

    data = await make_twitter_request(endpoint, params)

    if "error" in data:
        return {"tweets": [], "next_cursor": None, "error": data["error"]}

    tweets = data.get("tweets", [])
    next_cursor = data.get("next_cursor")

    return {"tweets": tweets, "next_cursor": next_cursor}


# ==================== 质量过滤 ====================
def filter_tweet(tweet: dict) -> bool:
    """
    判断推文是否符合质量标准

    Args:
        tweet: 推文数据

    Returns:
        是否通过过滤
    """
    author = tweet.get("author", {})
    is_verified = author.get("verified", False)

    # 蓝V用户阈值减半
    factor = 0.5 if is_verified else 1

    like_count = tweet.get("likeCount", 0) or 0
    retweet_count = tweet.get("retweetCount", 0) or 0
    view_count = tweet.get("viewCount", 0) or 0
    followers = author.get("followers", 0) or 0

    # 检查是否是回复推文
    tweet_type = tweet.get("type", "")
    if tweet_type and "reply" in tweet_type.lower():
        return False

    # 检查文本是否以 @ 开头 (回复)
    text = tweet.get("text", "")
    if text.startswith("@"):
        return False

    # 应用阈值
    if like_count < TWITTER_FILTER_CONFIG["minLikes"] * factor:
        return False
    if retweet_count < TWITTER_FILTER_CONFIG["minRetweets"] * factor:
        return False
    if view_count < TWITTER_FILTER_CONFIG["minViews"] * factor:
        return False
    if followers < TWITTER_FILTER_CONFIG["minFollowers"] * factor:
        return False

    return True


def sort_tweets_by_quality(tweets: list) -> list:
    """
    按质量评分排序推文

    Args:
        tweets: 推文列表

    Returns:
        排序后的推文列表
    """
    def quality_score(tweet):
        like_count = tweet.get("likeCount", 0) or 0
        retweet_count = tweet.get("retweetCount", 0) or 0
        view_count = tweet.get("viewCount", 0) or 0
        followers = tweet.get("author", {}).get("followers", 0) or 0

        # 加权评分
        return (
            like_count * 3 +
            retweet_count * 10 +
            view_count * 0.01 +
            followers * 0.001
        )

    return sorted(tweets, key=quality_score, reverse=True)


# ==================== 主测试函数 ====================
async def test_twitter_fetch(keyword: str = "Hermes Agent"):
    """
    测试 Twitter 数据抓取

    Args:
        keyword: 测试关键词
    """
    print("\n" + "="*60)
    print("Twitter 数据抓取测试")
    print("="*60)
    print(f"关键词: {keyword}")
    print(f"API Key: {TWITTER_API_KEY}")
    print(f"API Base: {TWITTER_API_BASE}")
    print("="*60 + "\n")

    all_tweets = []
    errors = []

    # 构建 Top 和 Latest 查询
    top_query = build_advanced_query(keyword, "Top")
    latest_query = build_advanced_query(keyword, "Latest")

    print(f"Top 查询: {top_query}")
    print(f"Latest 查询: {latest_query}\n")

    # 并行抓取 Top (第1页) 和 Latest
    print("-"*40)
    print("开始抓取...")
    print("-"*40)

    # Top 搜索第1页
    print("\n>>> 抓取 Top 第1页...")
    top_page1 = await fetch_tweet_page(top_query, "Top")

    if "error" in top_page1 and top_page1.get("tweets") == []:
        errors.append(f"Top 第1页失败: {top_page1['error']}")
        print(f"❌ Top 第1页失败: {top_page1['error']}")
    else:
        tweets = top_page1.get("tweets", [])
        print(f"✅ Top 第1页成功: {len(tweets)} 条推文")
        all_tweets.extend(tweets)

        # 如果有足够结果，尝试抓取 Top 第2页
        if len(tweets) >= 20 and top_page1.get("next_cursor"):
            print("\n>>> 抓取 Top 第2页...")
            await asyncio.sleep(1)  # 避免 rate limit
            top_page2 = await fetch_tweet_page(top_query, "Top", top_page1["next_cursor"])

            if "error" not in top_page2:
                tweets2 = top_page2.get("tweets", [])
                print(f"✅ Top 第2页成功: {len(tweets2)} 条推文")
                all_tweets.extend(tweets2)
            else:
                errors.append(f"Top 第2页失败: {top_page2['error']}")
                print(f"❌ Top 第2页失败: {top_page2['error']}")

    # Latest 搜索
    print("\n>>> 抓取 Latest...")
    await asyncio.sleep(1)  # 避免 rate limit
    latest_page = await fetch_tweet_page(latest_query, "Latest")

    if "error" in latest_page and latest_page.get("tweets") == []:
        errors.append(f"Latest 失败: {latest_page['error']}")
        print(f"❌ Latest 失败: {latest_page['error']}")
    else:
        tweets = latest_page.get("tweets", [])
        print(f"✅ Latest 成功: {len(tweets)} 条推文")
        all_tweets.extend(tweets)

    # 统计结果
    print("\n" + "-"*40)
    print("抓取结果统计")
    print("-"*40)
    print(f"总抓取数: {len(all_tweets)} 条")
    print(f"错误数: {len(errors)} 个")

    if errors:
        print("\n错误详情:")
        for err in errors:
            print(f"  - {err}")

    # 应用质量过滤
    print("\n" + "-"*40)
    print("质量过滤")
    print("-"*40)
    print(f"过滤阈值: minLikes={TWITTER_FILTER_CONFIG['minLikes']}, minRetweets={TWITTER_FILTER_CONFIG['minRetweets']}")

    filtered_tweets = [t for t in all_tweets if filter_tweet(t)]
    print(f"过滤后保留: {len(filtered_tweets)} 条")
    print(f"过滤掉: {len(all_tweets) - len(filtered_tweets)} 条")

    # 排序
    sorted_tweets = sort_tweets_by_quality(filtered_tweets)

    # 打印结果
    print("\n" + "="*60)
    print("最终结果")
    print("="*60)

    if sorted_tweets:
        print(f"\n共 {len(sorted_tweets)} 条高质量推文:")

        for i, tweet in enumerate(sorted_tweets[:10], 1):  # 只显示前10条
            author = tweet.get("author", {})
            print(f"\n[{i}] {tweet.get('text', '')[:100]}...")
            print(f"    作者: {author.get('username', 'N/A')} (粉丝: {author.get('followers', 0)})")
            print(f"    统计: 赞={tweet.get('likeCount', 0)}, 转={tweet.get('retweetCount', 0)}, 看={tweet.get('viewCount', 0)}")
            print(f"    时间: {tweet.get('createdAt', 'N/A')}")
            print(f"    URL: https://twitter.com/{author.get('username', '')}/status/{tweet.get('id', '')}")
    else:
        print("\n❌ 没有获取到有效推文")

        # 分析失败原因
        print("\n失败原因分析:")
        if any("404" in err for err in errors):
            print("  - HTTP 404: API endpoint 不存在，请检查 endpoint 是否正确")
            print("    当前使用: /twitter/tweet/advanced_search")
        if any("429" in err for err in errors):
            print("  - HTTP 429: Rate limit 达到限制，需要等待或更换 API Key")
        if any("超时" in err for err in errors):
            print("  - 网络超时: 请检查网络连接或增加 timeout 时间")
        if len(all_tweets) > 0 and len(filtered_tweets) == 0:
            print("  - 虽然抓取到推文，但全部被质量过滤掉")
            print(f"    原始推文数: {len(all_tweets)}，建议降低过滤阈值")

    print("\n" + "="*60)
    print("测试完成")
    print("="*60 + "\n")

    return sorted_tweets


# ==================== 主入口 ====================
if __name__ == "__main__":
    # 可以传入自定义关键词
    import argparse
    parser = argparse.ArgumentParser(description="测试 Twitter 数据抓取")
    parser.add_argument("--keyword", type=str, default="Hermes Agent", help="搜索关键词")
    args = parser.parse_args()

    asyncio.run(test_twitter_fetch(args.keyword))