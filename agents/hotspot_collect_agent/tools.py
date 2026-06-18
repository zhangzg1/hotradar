"""
数据抓取工具
实现各数据源的异步抓取功能
"""
import asyncio
import re
import json
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode, quote

import aiohttp
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from .state import SearchResult, AuthorInfo
from .config import (
    TWITTER_API_KEY,
    TWITTER_API_BASE,
    RATE_LIMITS,
    DEFAULT_FETCH_CONFIG,
)
from .utils import (
    get_random_user_agent,
    format_since_date,
    sort_twitter_by_quality,
)
from backend.common.logger import logger


# ==================== 频率限制器 ====================
class RateLimiter:
    """请求频率限制器"""

    def __init__(self, min_interval_ms: int):
        self.min_interval = min_interval_ms / 1000  # 转换为秒
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        """等待直到可以发起下一次请求"""
        async with self._lock:
            elapsed = asyncio.get_event_loop().time() - self.last_request_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_request_time = asyncio.get_event_loop().time()


# 各数据源的频率限制器
rate_limiters = {
    "twitter": RateLimiter(RATE_LIMITS.get("twitter", 0)),
    "youtube": RateLimiter(RATE_LIMITS.get("youtube", 1000)),
    "bing": RateLimiter(RATE_LIMITS.get("bing", 5000)),
    "sogou": RateLimiter(RATE_LIMITS.get("sogou", 3000)),
    "bilibili": RateLimiter(RATE_LIMITS.get("bilibili", 2000)),
    "douyin": RateLimiter(RATE_LIMITS.get("douyin", 3000)),
}


# ==================== Twitter 质量过滤 ====================
def filter_and_rank_tweets(
    tweets: List[SearchResult],
    quality_filter: Dict[str, Any] = None,
) -> List[SearchResult]:
    """
    Twitter 质量过滤和排序

    过滤规则:
    1. 排除回复推文（type字段 + 文本以@用户名开头）
    2. 蓝V用户阈值减半（minLikes * 0.5）
    3. 按质量评分排序

    Args:
        tweets: 推文列表
        quality_filter: 质量过滤配置

    Returns:
        过滤并排序后的推文列表
    """
    quality_filter = quality_filter or DEFAULT_FETCH_CONFIG.get("twitter", {}).get("qualityFilter", {})

    min_likes = quality_filter.get("minLikes", 10)
    min_retweets = quality_filter.get("minRetweets", 5)
    min_views = quality_filter.get("minViews", 500)
    min_followers = quality_filter.get("minFollowers", 100)

    filtered = []

    for tweet in tweets:
        # 排除回复推文：检查 type 字段
        tweet_type = tweet.get("type", "")
        if tweet_type and "reply" in tweet_type.lower():
            continue

        # 排除回复推文：检查文本是否以 @用户名 开头
        text = tweet.get("content", "").strip()
        if re.match(r"^@\w+\s", text):
            continue

        # 获取作者信息
        author = tweet.get("author", {})
        is_verified = author.get("verified", False)

        # 蓝V用户阈值减半
        factor = 0.5 if is_verified else 1

        # 应用过滤条件
        like_count = tweet.get("likeCount", 0) or 0
        retweet_count = tweet.get("retweetCount", 0) or 0
        view_count = tweet.get("viewCount", 0) or 0
        followers = author.get("followers", 0) or 0

        if like_count < min_likes * factor:
            continue
        if retweet_count < min_retweets * factor:
            continue
        if view_count < min_views * factor:
            continue
        if followers < min_followers * factor:
            continue

        filtered.append(tweet)

    # 按质量评分排序
    return sort_twitter_by_quality(filtered)


# ==================== Twitter 抓取 ====================
def build_twitter_query(keyword: str, search_type: str = "Top") -> str:
    """
    构建 Twitter 高级搜索 query

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

    # 时间限制
    days = 7 if search_type == "Top" else 3
    parts.append(f"since:{format_since_date(days)}")

    # Top 搜索额外要求
    if search_type == "Top":
        parts.append("min_faves:10")

    return " ".join(parts)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_twitter(
    keyword: str,
    config: Dict[str, Any] = None,
    user_id: str = None,
) -> List[SearchResult]:
    """
    从 Twitter API 抓取数据

    Args:
        keyword: 搜索关键词
        config: 抓取配置
        user_id: 用户 ID

    Returns:
        搜索结果列表
    """
    # 优先从 app_settings 读取 Twitter API Key
    twitter_api_key = TWITTER_API_KEY
    try:
        from backend.services.settings_service import get_settings
        settings = await get_settings(user_id)
        user_key = settings.get("twitterApiKey")
        if user_key:
            twitter_api_key = user_key
    except Exception:
        pass

    if not twitter_api_key:
        logger.warning("Twitter API Key 未配置，跳过 Twitter 抓取")
        return []

    config = config or DEFAULT_FETCH_CONFIG.get("twitter", {})
    results: List[SearchResult] = []

    try:
        await rate_limiters["twitter"].wait()

        # 策略: Top(2页) + Latest(1页)
        # 第一页 Top 搜索
        top_query = build_twitter_query(keyword, "Top")
        top_page1, next_cursor = await _fetch_twitter_page(top_query, "Top", keyword, api_key=twitter_api_key)
        results.extend(top_page1)

        # 第二页 Top 搜索 (如果有更多且有cursor)
        if len(top_page1) >= 20 and next_cursor:
            await asyncio.sleep(6)  # 免费用户 rate limit: 每5秒1次请求
            top_page2, _ = await _fetch_twitter_page(top_query, "Top", keyword, cursor=next_cursor, api_key=twitter_api_key)
            results.extend(top_page2)

        # Latest 搜索
        await asyncio.sleep(6)  # rate limit
        latest_query = build_twitter_query(keyword, "Latest")
        latest_results, _ = await _fetch_twitter_page(latest_query, "Latest", keyword, api_key=twitter_api_key)
        results.extend(latest_results)

        # 应用质量过滤和排序
        quality_filter = config.get("qualityFilter", {})
        results = filter_and_rank_tweets(results, quality_filter)

        # 截取到配置的数量
        max_results = config.get("maxResults", 60)
        results = results[:max_results]

        logger.info(f"Twitter 抓取完成: {len(results)} 条结果 (质量过滤后)")

    except Exception as e:
        logger.error(f"Twitter 抓取失败: {e}")

    return results


async def _fetch_twitter_page(
    query: str,
    search_type: str,
    keyword: str,
    cursor: str = None,
    api_key: str = None,
) -> tuple[List[SearchResult], Optional[str]]:
    """
    抓取 Twitter 单页结果

    Args:
        query: 查询字符串
        search_type: 搜索类型
        keyword: 原始关键词
        cursor: 分页游标 (可选)

    Returns:
        (搜索结果列表, 下一页游标)
    """
    results = []

    try:
        # 构建 API 请求 - 使用正确的 endpoint
        endpoint = "/twitter/tweet/advanced_search"
        params = {
            "query": query,
            "queryType": search_type,
        }

        # 添加 cursor 参数
        if cursor:
            params["cursor"] = cursor

        url = f"{TWITTER_API_BASE}{endpoint}?{urlencode(params)}"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={
                    "X-API-Key": api_key or TWITTER_API_KEY,
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.warning(f"Twitter API 返回非200状态: {response.status}, {error_text[:200]}")
                    return results, None

                data = await response.json()

        # 解析结果
        tweets = data.get("tweets", [])
        next_cursor = data.get("next_cursor")  # 获取下一页游标

        for tweet in tweets:
            result = _parse_twitter_tweet(tweet, keyword)
            if result:
                results.append(result)

        logger.info(f"Twitter {search_type} 页面抓取: {len(results)} 条结果")

    except Exception as e:
        logger.error(f"Twitter 单页抓取失败: {e}")

    return results, next_cursor


def _parse_twitter_tweet(tweet: Dict[str, Any], keyword: str) -> Optional[SearchResult]:
    """
    解析 Twitter 推文数据

    Args:
        tweet: 推文原始数据
        keyword: 原始关键词

    Returns:
        SearchResult 或 None
    """
    try:
        text = tweet.get("text", "")
        if not text:
            return None

        # 构建标题 (前100字符)
        title = text[:100] + "..." if len(text) > 100 else text

        # 作者信息
        author_data = tweet.get("author", {})
        author: Optional[AuthorInfo] = None
        if author_data:
            author = {
                "name": author_data.get("name", ""),
                "username": author_data.get("userName", ""),
                "avatar": author_data.get("profilePicture", ""),
                "followers": author_data.get("followers", 0),
                "verified": author_data.get("isBlueVerified", False),
            }

        # 发布时间
        created_at = tweet.get("createdAt", "")
        published_at = None
        if created_at:
            try:
                published_at = created_at
            except:
                pass

        return {
            "title": title,
            "content": text,
            "url": tweet.get("url", ""),
            "source": "twitter",
            "sourceId": tweet.get("id", ""),
            "publishedAt": published_at,
            "viewCount": tweet.get("viewCount", 0),
            "likeCount": tweet.get("likeCount", 0),
            "retweetCount": tweet.get("retweetCount", 0),
            "replyCount": tweet.get("replyCount", 0),
            "quoteCount": tweet.get("quoteCount", 0),
            "author": author,
        }

    except Exception as e:
        logger.warning(f"解析 Twitter 推文失败: {e}")
        return None


# ==================== Bing 抓取 ====================
def _decode_bing_redirect_url(bing_url: str) -> str:
    """
    解析 Bing 重定向链接，提取真实 URL

    Bing 重定向链接格式: https://www.bing.com/ck/a?!&&p=...&u=a1aHR0cHM6Ly9...

    Args:
        bing_url: Bing 重定向链接

    Returns:
        真实 URL，如果解析失败返回原链接
    """
    import base64

    if not bing_url.startswith("https://www.bing.com/ck/a?"):
        return bing_url

    try:
        # 查找 u= 参数
        import re
        match = re.search(r'u=a1([a-zA-Z0-9+/=]+)', bing_url)
        if match:
            encoded_url = match.group(1)
            # 修复 Base64 padding (长度需要是4的倍数)
            missing_padding = len(encoded_url) % 4
            if missing_padding:
                encoded_url += '=' * (4 - missing_padding)
            # Base64 解码
            decoded = base64.b64decode(encoded_url).decode('utf-8')
            return decoded
    except Exception as e:
        logger.warning(f"解析 Bing 重定向链接失败: {e}")

    return bing_url


def _get_bing_headers() -> Dict[str, str]:
    """
    生成 Bing 请求头，模拟真实浏览器
    """
    ua = get_random_user_agent()
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "Referer": "https://www.bing.com/",
    }


def _get_bing_cookies() -> str:
    """
    生成 Bing 必要的 cookies
    """
    import uuid
    # Bing 需要 _EDGE_S 和 _EDGE_V cookie
    edge_s = f"S={uuid.uuid4().hex}&GUID={uuid.uuid4().hex}"
    edge_v = f"V={uuid.uuid4().hex}"
    muid = uuid.uuid4().hex
    return f"_EDGE_S={edge_s}; _EDGE_V={edge_v}; MUID={muid}; _RwBf=ilt=1"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_bing(
    keyword: str,
    config: Dict[str, Any] = None,
    user_id: str = None,
) -> List[SearchResult]:
    """
    从 Bing 搜索抓取数据 (HTML爬虫)

    Args:
        keyword: 搜索关键词
        config: 抓取配置

    Returns:
        搜索结果列表
    """
    config = config or DEFAULT_FETCH_CONFIG.get("bing", {})
    results: List[SearchResult] = []

    try:
        await rate_limiters["bing"].wait()

        url = "https://www.bing.com/search"
        params = {
            "q": keyword,
            "count": config.get("maxResults", 20),
            "setlang": "en",
            "cc": "US",
        }

        headers = _get_bing_headers()
        headers["Cookie"] = _get_bing_cookies()

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=True,
            ) as response:
                if response.status != 200:
                    logger.warning(f"Bing 返回非200状态: {response.status}")
                    return results

                html = await response.text()

        # 解析 HTML
        soup = BeautifulSoup(html, "lxml")

        # 检查是否是验证码页面
        captcha = soup.select_one(".captcha, #captcha, .b_wlBlRaceCaptcha")
        if captcha:
            logger.warning("Bing 返回验证码页面，可能被反爬拦截")
            return results

        # Bing 搜索结果容器
        for item in soup.select("li.b_algo"):
            title_elem = item.select_one("h2 a")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            link = title_elem.get("href", "")

            # 解析 Bing 重定向链接获取真实 URL
            real_url = _decode_bing_redirect_url(link)

            # 摘要
            snippet_elem = item.select_one(".b_caption p")
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

            if title and real_url and real_url.startswith("http"):
                results.append({
                    "title": title,
                    "content": snippet or title,
                    "url": real_url,
                    "source": "bing",
                })

        logger.info(f"Bing 抓取完成: {len(results)} 条结果")

    except Exception as e:
        logger.error(f"Bing 抓取失败: {e}")

    return results


# ==================== 搜狗 抓取 ====================
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_sogou(
    keyword: str,
    config: Dict[str, Any] = None,
    user_id: str = None,
) -> List[SearchResult]:
    """
    从搜狗搜索抓取数据 (HTML爬虫)

    Args:
        keyword: 搜索关键词
        config: 抓取配置

    Returns:
        搜索结果列表
    """
    config = config or DEFAULT_FETCH_CONFIG.get("sogou", {})
    results: List[SearchResult] = []

    try:
        await rate_limiters["sogou"].wait()

        url = "https://www.sogou.com/web"
        params = {
            "query": keyword,
            "ie": "utf-8",
        }

        headers = {
            "User-Agent": get_random_user_agent(),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status != 200:
                    logger.warning(f"搜狗返回非200状态: {response.status}")
                    return results

                html = await response.text()

        # 解析 HTML
        soup = BeautifulSoup(html, "lxml")

        # 搜狗结果容器
        for item in soup.select(".vrwrap, .rb"):
            # 标题
            title_elem = item.select_one("h3 a, .vr-title a, .vrTitle a")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)

            # 过滤"大家还在搜"
            if "大家还在搜" in title:
                continue

            link = title_elem.get("href", "")

            # 搜狗相对路径转换
            if link.startswith("/link?url="):
                link = f"https://www.sogou.com{link}"

            # 摘要
            snippet_elem = item.select_one(".space-txt, .str-text-info, .str_info")
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

            if title and link:
                results.append({
                    "title": title,
                    "content": snippet or title,
                    "url": link,
                    "source": "sogou",
                })

        logger.info(f"搜狗抓取完成: {len(results)} 条结果")

    except Exception as e:
        logger.error(f"搜狗抓取失败: {e}")

    return results


# ==================== Bilibili 抓取 ====================
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_bilibili(
    keyword: str,
    config: Dict[str, Any] = None,
    user_id: str = None,
) -> List[SearchResult]:
    """
    从 Bilibili 抓取数据 (公开JSON API)

    Args:
        keyword: 搜索关键词
        config: 抓取配置

    Returns:
        搜索结果列表
    """
    config = config or DEFAULT_FETCH_CONFIG.get("bilibili", {})
    results: List[SearchResult] = []

    try:
        await rate_limiters["bilibili"].wait()

        # 生成 buvid3 cookie
        buvid3 = f"{uuid.uuid4()}infoc"

        url = "https://api.bilibili.com/x/web-interface/search/type"
        params = {
            "keyword": keyword,
            "search_type": "video",
            "order": config.get("orderBy", "pubdate"),
            "page": 1,
            "pagesize": config.get("maxResults", 20),
        }

        headers = {
            "User-Agent": get_random_user_agent(),
            "Referer": "https://search.bilibili.com/",
            "Cookie": f"buvid3={buvid3}",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status != 200:
                    logger.warning(f"Bilibili 返回非200状态: {response.status}")
                    return results

                data = await response.json()

        # 解析结果
        if data.get("code", 0) != 0:
            logger.warning(f"Bilibili API 返回错误: {data.get('message', '')}")
            return results

        result_list = data.get("data", {}).get("result", [])
        for video in result_list:
            # 去掉高亮标签
            title = video.get("title", "")
            title = re.sub(r"</?em[^>]*>", "", title)

            bvid = video.get("bvid", "")
            if not bvid:
                continue

            author: Optional[AuthorInfo] = None
            author_name = video.get("author", "")
            if author_name:
                author = {
                    "name": author_name,
                    "username": str(video.get("mid", "")),
                }

            # 发布时间转换
            pubdate = video.get("pubdate", 0)
            published_at = None
            if pubdate:
                published_at = datetime.fromtimestamp(pubdate).isoformat()

            results.append({
                "title": title,
                "content": video.get("description") or title,
                "url": f"https://www.bilibili.com/video/{bvid}",
                "source": "bilibili",
                "sourceId": bvid,
                "publishedAt": published_at,
                "viewCount": video.get("play", 0),
                "likeCount": video.get("like", 0),
                "commentCount": video.get("review", 0),
                "danmakuCount": video.get("danmaku", 0),
                "author": author,
            })

        logger.info(f"Bilibili 抓取完成: {len(results)} 条结果")

    except Exception as e:
        logger.error(f"Bilibili 抓取失败: {e}")

    return results


# ==================== 抖音 抓取 ====================
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_douyin(
    keyword: str,
    config: Dict[str, Any] = None,
    user_id: str = None,
) -> List[SearchResult]:
    """
    从抖音搜索抓取数据 (纯HTTP API)

    Args:
        keyword: 搜索关键词
        config: 抓取配置
        user_id: 用户 ID

    Returns:
        搜索结果列表
    """
    config = config or DEFAULT_FETCH_CONFIG.get("douyin", {})
    results: List[SearchResult] = []

    try:
        await rate_limiters["douyin"].wait()

        # 使用DouyinFetcher进行搜索（优先从数据库加载 Cookie）
        from .douyin_auth.douyin_fetcher import DouyinFetcher

        fetcher = await DouyinFetcher.create_from_db(user_id=user_id)

        if not fetcher.cookie:
            logger.warning("抖音Cookie未配置，跳过抖音抓取")
            return results

        max_count = config.get("maxResults", 20)
        raw_results = await fetcher.search(keyword, max_count=max_count)

        # 转换为SearchResult格式
        for video in raw_results:
            author: Optional[AuthorInfo] = None
            author_data = video.get("author", {})
            if author_data:
                author = {
                    "name": author_data.get("name", ""),
                    "username": author_data.get("username", ""),
                }

            # 发布时间转换
            published_at = None
            create_time = video.get("publishedAt", 0)
            if create_time:
                try:
                    published_at = datetime.fromtimestamp(create_time).isoformat()
                except Exception:
                    pass

            results.append({
                "title": video.get("title", ""),
                "content": video.get("desc", ""),
                "url": video.get("url", ""),
                "source": "douyin",
                "sourceId": video.get("aweme_id", ""),
                "publishedAt": published_at,
                "viewCount": video.get("viewCount", 0),
                "likeCount": video.get("likeCount", 0),
                "commentCount": video.get("commentCount", 0),
                "author": author,
            })

        logger.info(f"抖音抓取完成: {len(results)} 条结果")

    except Exception as e:
        logger.error(f"抖音抓取失败: {e}")

    return results


# ==================== YouTube 抓取 ====================
async def fetch_youtube(keyword: str, config: Dict[str, Any] = None, user_id: str = None) -> List[SearchResult]:
    """
    抓取YouTube视频数据

    使用 YouTube Data API v3 搜索视频，获取结构化数据

    Args:
        keyword: 搜索关键词
        config: 抓取配置（maxResults, order）

    Returns:
        SearchResult 列表
    """
    config = config or {}
    results: List[SearchResult] = []
    max_count = config.get("maxResults", 20)
    order = config.get("order", "relevance")

    try:
        await rate_limiters["youtube"].wait()

        from .youtube_auth.youtube_fetcher import YouTubeFetcher
        fetcher = YouTubeFetcher()

        if not fetcher.available:
            logger.warning("YouTube API Key 未配置，跳过")
            return results

        raw_results = await fetcher.search(keyword, max_count=max_count, order=order)
        logger.info(f"YouTube 原始结果: {len(raw_results)} 条")

        for video in raw_results:
            author_info = video.get("author", {})
            author = None
            if author_info:
                author = {
                    "name": author_info.get("name", ""),
                    "username": author_info.get("username", ""),
                }

            results.append(SearchResult(
                title=video.get("title", ""),
                content=video.get("desc", ""),
                url=video.get("url", ""),
                source="youtube",
                sourceId=video.get("video_id", ""),
                publishedAt=video.get("publishedAt", ""),
                viewCount=video.get("viewCount", 0),
                likeCount=video.get("likeCount", 0),
                commentCount=video.get("commentCount", 0),
                author=author,
            ))

        logger.info(f"YouTube抓取完成: {len(results)} 条结果")

    except Exception as e:
        logger.error(f"YouTube抓取失败: {e}")

    return results


# ==================== 统一抓取入口 ====================
async def fetch_all_sources(
    keyword: str,
    fetch_config: Dict[str, Any] = None,
    sources: List[str] = None,
    user_id: str = None,
) -> List[SearchResult]:
    """
    并行抓取所有数据源

    Args:
        keyword: 搜索关键词
        fetch_config: 抓取配置
        sources: 要抓取的数据源列表
        user_id: 用户 ID

    Returns:
        所有数据源的搜索结果合并列表
    """
    fetch_config = fetch_config or DEFAULT_FETCH_CONFIG
    sources = sources or ["twitter", "youtube", "bilibili", "douyin", "bing", "sogou"]

    # 构建抓取任务
    tasks = []
    source_map = {
        "twitter": fetch_twitter,
        "youtube": fetch_youtube,
        "bilibili": fetch_bilibili,
        "douyin": fetch_douyin,
        "bing": fetch_bing,
        "sogou": fetch_sogou,
    }

    for source in sources:
        if source in source_map:
            config = fetch_config.get(source, {})
            tasks.append(source_map[source](keyword, config, user_id=user_id))

    # 并行执行
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    # 合并结果
    all_results: List[SearchResult] = []
    for i, result in enumerate(results_list):
        if isinstance(result, Exception):
            logger.error(f"数据源 {sources[i]} 抓取异常: {result}")
        elif isinstance(result, list):
            all_results.extend(result)

    logger.info(f"所有数据源抓取完成: 共 {len(all_results)} 条结果")

    return all_results