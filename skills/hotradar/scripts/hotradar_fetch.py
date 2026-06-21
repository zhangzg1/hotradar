#!/usr/bin/env python3
"""
HotRadar - 独立热点数据采集脚本

从多个数据源并行采集热点信息，进行去重和质量过滤，输出 JSON 结果。
不依赖项目的 backend/llm 模块，可独立运行。

用法:
    python hotradar_fetch.py <config.json> <output.json>

配置文件格式:
{
    "keywords": ["codex", "openclaw"],
    "sources": {
        "bing": {"enabled": true, "maxResults": 2},
        "sogou": {"enabled": true, "maxResults": 1},
        "bilibili": {"enabled": true, "maxResults": 3, "orderBy": "pubdate"},
        "twitter": {"enabled": false, "apiKey": "", "maxResults": 8},
        "youtube": {"enabled": false, "apiKey": "", "maxResults": 8},
        "douyin": {"enabled": false, "cookie": "", "maxResults": 3}
    },
    "maxAgeHours": 168,
    "qualityFilter": {
        "minTitleLength": 5,
        "minContentLength": 20
    }
}

关键设计:
    - 每个关键词单独搜索，多关键词并行
    - maxResults 是用户设置的每个数据源抓取数量，脚本内部有硬上限约束
    - 只用用户原始关键词搜索，不做关键词变体扩展搜索
"""
import asyncio
import json
import re
import sys
import uuid
import base64
import random
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode

import aiohttp
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("hotradar")

# ==================== 常量配置 ====================
TWITTER_API_BASE = "https://api.twitterapi.io"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
SOURCE_PRIORITY = {"twitter": 1, "youtube": 2, "bilibili": 3, "douyin": 4, "bing": 5, "sogou": 6}

# 每个数据源的抓取数量硬上限（用户设置的 maxResults 不能超过此值）
MAX_RESULTS_CAP = {"twitter": 20, "youtube": 20, "bilibili": 20, "douyin": 20, "bing": 10, "sogou": 10}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

RATE_LIMITS_MS = {"twitter": 0, "youtube": 1000, "bing": 5000, "sogou": 3000, "bilibili": 2000, "douyin": 3000}


# ==================== 频率限制器 ====================
class RateLimiter:
    def __init__(self, min_interval_ms: int):
        self.min_interval = min_interval_ms / 1000
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()

    async def wait(self):
        async with self._lock:
            elapsed = asyncio.get_event_loop().time() - self.last_request_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_request_time = asyncio.get_event_loop().time()


rate_limiters = {s: RateLimiter(RATE_LIMITS_MS.get(s, 2000)) for s in SOURCE_PRIORITY}


def get_random_ua() -> str:
    return random.choice(USER_AGENTS)


# ==================== Bing 抓取 ====================
def _decode_bing_redirect(bing_url: str) -> str:
    if not bing_url.startswith("https://www.bing.com/ck/a?"):
        return bing_url
    try:
        match = re.search(r'u=a1([a-zA-Z0-9+/=]+)', bing_url)
        if match:
            encoded = match.group(1)
            padding = len(encoded) % 4
            if padding:
                encoded += '=' * (4 - padding)
            return base64.b64decode(encoded).decode('utf-8')
    except Exception:
        pass
    return bing_url


def _get_bing_headers() -> Dict[str, str]:
    ua = get_random_ua()
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
    edge_s = f"S={uuid.uuid4().hex}&GUID={uuid.uuid4().hex}"
    edge_v = f"V={uuid.uuid4().hex}"
    muid = uuid.uuid4().hex
    return f"_EDGE_S={edge_s}; _EDGE_V={edge_v}; MUID={muid}; _RwBf=ilt=1"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_bing(search_query: str, config: Dict) -> List[Dict]:
    results = []
    try:
        await rate_limiters["bing"].wait()
        params = {"q": search_query, "count": config.get("maxResults", 10), "setlang": "en", "cc": "US"}
        headers = _get_bing_headers()
        headers["Cookie"] = _get_bing_cookies()

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.bing.com/search",
                params=params, headers=headers,
                timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Bing status={resp.status}")
                    return results
                html = await resp.text()

        soup = BeautifulSoup(html, "lxml")
        if soup.select_one(".captcha, #captcha, .b_wlBlRaceCaptcha"):
            logger.warning("Bing captcha detected")
            return results

        for item in soup.select("li.b_algo"):
            title_el = item.select_one("h2 a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = _decode_bing_redirect(title_el.get("href", ""))
            snippet_el = item.select_one(".b_caption p")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            if title and link and link.startswith("http"):
                results.append({"title": title, "content": snippet or title, "url": link, "source": "bing"})

        logger.info(f"Bing: {len(results)} results")
    except Exception as e:
        logger.error(f"Bing fetch error: {e}")
    return results


# ==================== 搜狗抓取 ====================
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_sogou(search_query: str, config: Dict) -> List[Dict]:
    results = []
    try:
        await rate_limiters["sogou"].wait()
        headers = {"User-Agent": get_random_ua(), "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.sogou.com/web",
                params={"query": search_query, "ie": "utf-8"}, headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Sogou status={resp.status}")
                    return results
                html = await resp.text()

        soup = BeautifulSoup(html, "lxml")
        for item in soup.select(".vrwrap, .rb"):
            title_el = item.select_one("h3 a, .vr-title a, .vrTitle a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if "大家还在搜" in title:
                continue
            link = title_el.get("href", "")
            if link.startswith("/link?url="):
                link = f"https://www.sogou.com{link}"
            snippet_el = item.select_one(".space-txt, .str-text-info, .str_info")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            if title and link:
                results.append({"title": title, "content": snippet or title, "url": link, "source": "sogou"})

        logger.info(f"Sogou: {len(results)} results")
    except Exception as e:
        logger.error(f"Sogou fetch error: {e}")
    return results


# ==================== Bilibili 抓取 ====================
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_bilibili(search_query: str, config: Dict) -> List[Dict]:
    results = []
    try:
        await rate_limiters["bilibili"].wait()
        buvid3 = f"{uuid.uuid4()}infoc"
        params = {
            "keyword": search_query, "search_type": "video",
            "order": config.get("orderBy", "pubdate"), "page": 1,
            "pagesize": config.get("maxResults", 20),
        }
        headers = {
            "User-Agent": get_random_ua(),
            "Referer": "https://search.bilibili.com/",
            "Cookie": f"buvid3={buvid3}",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.bilibili.com/x/web-interface/search/type",
                params=params, headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Bilibili status={resp.status}")
                    return results
                data = await resp.json()

        if data.get("code", 0) != 0:
            logger.warning(f"Bilibili API error: {data.get('message', '')}")
            return results

        for video in data.get("data", {}).get("result", []):
            title = re.sub(r"</?em[^>]*>", "", video.get("title", ""))
            bvid = video.get("bvid", "")
            if not bvid:
                continue
            pubdate = video.get("pubdate", 0)
            published_at = datetime.fromtimestamp(pubdate).isoformat() if pubdate else None
            author_name = video.get("author", "")
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
                "author": {"name": author_name, "username": str(video.get("mid", ""))} if author_name else None,
            })

        logger.info(f"Bilibili: {len(results)} results")
    except Exception as e:
        logger.error(f"Bilibili fetch error: {e}")
    return results


# ==================== Twitter 抓取 ====================
def _build_twitter_query(search_query: str, search_type: str = "Top") -> str:
    parts = [search_query, "-filter:retweets", "-filter:replies"]
    days = 7 if search_type == "Top" else 3
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    parts.append(f"since:{since}")
    if search_type == "Top":
        parts.append("min_faves:10")
    return " ".join(parts)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_twitter(search_query: str, config: Dict) -> List[Dict]:
    api_key = config.get("apiKey", "")
    if not api_key:
        logger.warning("Twitter: no API key, skipping")
        return []

    results = []
    try:
        await rate_limiters["twitter"].wait()

        # Top search page 1
        top_query = _build_twitter_query(search_query, "Top")
        page1, next_cursor = await _fetch_twitter_page(top_query, "Top", api_key)
        results.extend(page1)

        # Top search page 2
        if len(page1) >= 20 and next_cursor:
            await asyncio.sleep(6)
            page2, _ = await _fetch_twitter_page(top_query, "Top", api_key, cursor=next_cursor)
            results.extend(page2)

        # Latest search
        await asyncio.sleep(6)
        latest_query = _build_twitter_query(search_query, "Latest")
        latest, _ = await _fetch_twitter_page(latest_query, "Latest", api_key)
        results.extend(latest)

        # Quality filter and sort
        results = _filter_rank_tweets(results, config.get("qualityFilter", {}))
        max_results = config.get("maxResults", 60)
        results = results[:max_results]

        logger.info(f"Twitter: {len(results)} results")
    except Exception as e:
        logger.error(f"Twitter fetch error: {e}")
    return results


async def _fetch_twitter_page(query: str, search_type: str, api_key: str, cursor: str = None) -> tuple:
    results = []
    next_cursor = None
    try:
        endpoint = "/twitter/tweet/advanced_search"
        params = {"query": query, "queryType": search_type}
        if cursor:
            params["cursor"] = cursor
        url = f"{TWITTER_API_BASE}{endpoint}?{urlencode(params)}"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    return results, None
                data = await resp.json()

        next_cursor = data.get("next_cursor")
        for tweet in data.get("tweets", []):
            text = tweet.get("text", "")
            if not text:
                continue
            author_data = tweet.get("author", {})
            results.append({
                "title": text[:100] + "..." if len(text) > 100 else text,
                "content": text,
                "url": tweet.get("url", ""),
                "source": "twitter",
                "sourceId": tweet.get("id", ""),
                "publishedAt": tweet.get("createdAt"),
                "viewCount": tweet.get("viewCount", 0),
                "likeCount": tweet.get("likeCount", 0),
                "retweetCount": tweet.get("retweetCount", 0),
                "replyCount": tweet.get("replyCount", 0),
                "quoteCount": tweet.get("quoteCount", 0),
                "type": tweet.get("type", ""),
                "author": {
                    "name": author_data.get("name", ""),
                    "username": author_data.get("userName", ""),
                    "avatar": author_data.get("profilePicture", ""),
                    "followers": author_data.get("followers", 0),
                    "verified": author_data.get("isBlueVerified", False),
                } if author_data else None,
            })
    except Exception as e:
        logger.error(f"Twitter page fetch error: {e}")
    return results, next_cursor


def _filter_rank_tweets(tweets: List[Dict], quality_filter: Dict = None) -> List[Dict]:
    qf = quality_filter or {}
    min_likes = qf.get("minLikes", 10)
    min_retweets = qf.get("minRetweets", 5)
    min_views = qf.get("minViews", 500)
    min_followers = qf.get("minFollowers", 100)

    filtered = []
    for t in tweets:
        # 排除回复推文：检查 type 字段
        tweet_type = t.get("type", "")
        if tweet_type and "reply" in tweet_type.lower():
            continue

        # 排除回复推文：检查文本是否以 @用户名 开头
        text = t.get("content", "").strip()
        if re.match(r"^@\w+\s", text):
            continue

        author = t.get("author") or {}
        is_verified = author.get("verified", False)

        # 蓝V用户阈值减半
        factor = 0.5 if is_verified else 1

        if (t.get("likeCount") or 0) < min_likes * factor:
            continue
        if (t.get("retweetCount") or 0) < min_retweets * factor:
            continue
        if (t.get("viewCount") or 0) < min_views * factor:
            continue
        if (author.get("followers") or 0) < min_followers * factor:
            continue

        filtered.append(t)

    # Sort by quality score
    def score(t):
        likes = t.get("likeCount", 0) or 0
        rts = t.get("retweetCount", 0) or 0
        views = t.get("viewCount", 0) or 0
        s = likes * 2 + rts * 3 + views // 100
        if (t.get("author") or {}).get("verified"):
            s += 50
        return s
    return sorted(filtered, key=score, reverse=True)


# ==================== YouTube 抓取 ====================
def _parse_duration(duration: str) -> int:
    if not duration:
        return 0
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_youtube(search_query: str, config: Dict) -> List[Dict]:
    api_key = config.get("apiKey", "")
    if not api_key:
        logger.warning("YouTube: no API key, skipping")
        return []

    results = []
    max_count = config.get("maxResults", 20)
    order = config.get("order", "relevance")

    try:
        await rate_limiters["youtube"].wait()

        # 时间过滤：最近7天
        published_after = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        async with aiohttp.ClientSession() as session:
            page_token = None
            search_results = []

            while len(search_results) < max_count:
                # Step 1: 搜索视频
                search_params = {
                    "part": "snippet",
                    "q": search_query,
                    "type": "video",
                    "maxResults": min(50, max_count - len(search_results)),
                    "order": order,
                    "videoDefinition": "any",
                    "publishedAfter": published_after,
                    "key": api_key,
                }
                if page_token:
                    search_params["pageToken"] = page_token

                async with session.get(
                    f"{YOUTUBE_API_BASE}/search",
                    params=search_params,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        logger.warning(f"YouTube API error: {resp.status} {error[:200]}")
                        break
                    data = await resp.json()

                if "error" in data:
                    logger.warning(f"YouTube API error: {data['error'].get('message', '')}")
                    break

                items = data.get("items", [])
                if not items:
                    break

                # 收集视频ID，用于批量获取统计信息
                video_ids = []
                page_results = []
                for item in items:
                    video_id = item.get("id", {}).get("videoId", "")
                    if not video_id:
                        continue
                    snippet = item.get("snippet", {})
                    page_results.append({
                        "video_id": video_id,
                        "title": snippet.get("title", ""),
                        "content": snippet.get("description", ""),
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "source": "youtube",
                        "sourceId": video_id,
                        "publishedAt": snippet.get("publishedAt", ""),
                        "author": {"name": snippet.get("channelTitle", "")} if snippet.get("channelTitle") else None,
                    })
                    video_ids.append(video_id)

                # Step 2: 批量获取视频统计信息
                if video_ids:
                    stats_params = {
                        "part": "statistics,contentDetails",
                        "id": ",".join(video_ids),
                        "key": api_key,
                    }
                    try:
                        async with session.get(
                            f"{YOUTUBE_API_BASE}/videos",
                            params=stats_params,
                            timeout=aiohttp.ClientTimeout(total=15),
                        ) as stats_resp:
                            if stats_resp.status == 200:
                                stats_data = await stats_resp.json()
                                stats_map = {}
                                for stat_item in stats_data.get("items", []):
                                    vid = stat_item.get("id", "")
                                    statistics = stat_item.get("statistics", {})
                                    content_details = stat_item.get("contentDetails", {})
                                    stats_map[vid] = {
                                        "viewCount": int(statistics.get("viewCount", 0)),
                                        "likeCount": int(statistics.get("likeCount", 0)),
                                        "commentCount": int(statistics.get("commentCount", 0)),
                                        "duration": _parse_duration(content_details.get("duration", "")),
                                    }

                                # 合并统计信息到搜索结果
                                for pr in page_results:
                                    vid = pr["video_id"]
                                    if vid in stats_map:
                                        pr["viewCount"] = stats_map[vid]["viewCount"]
                                        pr["likeCount"] = stats_map[vid]["likeCount"]
                                        pr["commentCount"] = stats_map[vid]["commentCount"]
                                        pr["duration"] = stats_map[vid]["duration"]
                                    else:
                                        pr["viewCount"] = 0
                                        pr["likeCount"] = 0
                                        pr["commentCount"] = 0
                                        pr["duration"] = 0
                    except Exception as e:
                        logger.warning(f"YouTube stats fetch error: {e}")

                search_results.extend(page_results)

                # 检查分页
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
                await asyncio.sleep(random.uniform(0.5, 1.5))

            results = search_results[:max_count]

        # 清理内部字段
        for r in results:
            r.pop("video_id", None)

        logger.info(f"YouTube: {len(results)} results")
    except Exception as e:
        logger.error(f"YouTube fetch error: {e}")
    return results


# ==================== 抖音抓取 ====================
def _get_douyin_web_id() -> str:
    def e(t):
        if t is not None:
            return str(t ^ (int(16 * random.random()) >> (t // 4)))
        else:
            return ''.join([
                str(int(1e7)), '-', str(int(1e3)), '-', str(int(4e3)),
                '-', str(int(8e3)), '-', str(int(1e11))
            ])
    web_id = ''.join(e(int(x)) if x in '018' else x for x in e(None))
    return web_id.replace('-', '')[:19]


def _build_douyin_common_params() -> Dict:
    return {
        "device_platform": "webapp",
        "aid": "6383",
        "channel": "channel_pc_web",
        "version_code": "190600",
        "version_name": "19.6.0",
        "update_version_code": "170400",
        "pc_client_type": "1",
        "cookie_enabled": "true",
        "browser_language": "zh-CN",
        "browser_platform": "MacIntel",
        "browser_name": "Chrome",
        "browser_version": "125.0.0.0",
        "browser_online": "true",
        "engine_name": "Blink",
        "os_name": "Mac OS",
        "os_version": "10.15.7",
        "cpu_core_num": "8",
        "device_memory": "8",
        "engine_version": "109.0",
        "platform": "PC",
        "screen_width": "2560",
        "screen_height": "1440",
        "effective_type": "4g",
        "round_trip_time": "50",
        "webid": _get_douyin_web_id(),
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_douyin(search_query: str, config: Dict) -> List[Dict]:
    cookie = config.get("cookie", "")
    if not cookie:
        logger.warning("Douyin: no cookie, skipping")
        return []

    results = []
    max_count = config.get("maxResults", 20)

    try:
        await rate_limiters["douyin"].wait()
        headers = {
            "User-Agent": get_random_ua(),
            "Referer": f"https://www.douyin.com/search/{search_query}",
            "Cookie": cookie,
            "Host": "www.douyin.com",
            "Origin": "https://www.douyin.com",
            "Content-Type": "application/json;charset=UTF-8",
        }

        async with aiohttp.ClientSession() as session:
            offset = 0
            search_id = ""

            while len(results) < max_count:
                query_params = {
                    "search_channel": "aweme_general",
                    "enable_history": "1",
                    "keyword": search_query,
                    "search_source": "tab_search",
                    "query_correct_type": "1",
                    "is_filter_search": "0",
                    "offset": offset,
                    "count": "15",
                    "need_filter_settings": "1",
                    "list_type": "multi",
                    "search_id": search_id,
                }
                query_params.update(_build_douyin_common_params())

                # 从 cookie 中提取 msToken
                ms_token = ""
                for part in cookie.split(";"):
                    part = part.strip()
                    if part.startswith("msToken="):
                        ms_token = part.split("=", 1)[1]
                        break
                if ms_token:
                    query_params["msToken"] = ms_token

                async with session.get(
                    "https://www.douyin.com/aweme/v1/web/general/search/single/",
                    params=query_params, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"Douyin status={resp.status}")
                        break
                    data = await resp.json()

                # 检查验证
                nil_info = data.get("search_nil_info", {})
                if nil_info.get("search_nil_type") == "verify_check":
                    logger.warning("Douyin verify check triggered")
                    break

                if not data.get("data"):
                    break

                for item in data.get("data", []):
                    aweme = item.get("aweme_info") or item.get("aweme_mix_info", {}).get("mix_items", [{}])[0]
                    if not aweme:
                        continue
                    aweme_id = aweme.get("aweme_id", "")
                    desc = aweme.get("desc", "")
                    author_data = aweme.get("author", {})
                    create_time = aweme.get("create_time", 0)
                    published_at = datetime.fromtimestamp(create_time).isoformat() if create_time else None
                    stats = aweme.get("statistics", {})
                    results.append({
                        "title": desc[:100] if desc else "",
                        "content": desc,
                        "url": f"https://www.douyin.com/video/{aweme_id}" if aweme_id else "",
                        "source": "douyin",
                        "sourceId": aweme_id,
                        "publishedAt": published_at,
                        "viewCount": stats.get("play_count", 0),
                        "likeCount": stats.get("digg_count", 0),
                        "commentCount": stats.get("comment_count", 0),
                        "shareCount": stats.get("share_count", 0),
                        "author": {
                            "name": author_data.get("nickname", ""),
                            "username": author_data.get("unique_id", "") or author_data.get("sec_uid", ""),
                        } if author_data else None,
                    })

                    if len(results) >= max_count:
                        break

                # 更新分页参数
                search_id = data.get("extra", {}).get("logid", "")
                offset += 15
                await asyncio.sleep(random.uniform(1, 2))

        results = results[:max_count]
        logger.info(f"Douyin: {len(results)} results")
    except Exception as e:
        logger.error(f"Douyin fetch error: {e}")
    return results


# ==================== 过滤工具 ====================
def normalize_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip().rstrip("/")
    url = re.sub(r"^https?://www\.", "https://", url)
    url = re.sub(r"^http://", "https://", url)
    return url


def deduplicate_by_url(results: List[Dict]) -> List[Dict]:
    unique = {}
    for item in results:
        nurl = normalize_url(item.get("url", ""))
        if not nurl:
            continue
        if nurl in unique:
            existing = unique[nurl]
            if SOURCE_PRIORITY.get(item.get("source", ""), 99) < SOURCE_PRIORITY.get(existing.get("source", ""), 99):
                unique[nurl] = item
        else:
            unique[nurl] = item
    return list(unique.values())


def quality_filter(results: List[Dict], config: Dict) -> List[Dict]:
    min_title = config.get("minTitleLength", 5)
    min_content = config.get("minContentLength", 20)
    filtered = []
    for item in results:
        title = item.get("title", "")
        content = item.get("content", "")
        url = item.get("url", "")
        if not title or len(title.strip()) < min_title:
            continue
        if not content or len(content.strip()) < min_content:
            continue
        if not url or not url.startswith("http"):
            continue
        filtered.append(item)
    return filtered


def time_filter(results: List[Dict], max_hours: int) -> List[Dict]:
    cutoff = datetime.now() - timedelta(hours=max_hours)
    filtered = []
    for item in results:
        pub = item.get("publishedAt")
        if not pub:
            filtered.append(item)
            continue
        try:
            if isinstance(pub, str):
                pub_time = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            elif isinstance(pub, datetime):
                pub_time = pub
            else:
                filtered.append(item)
                continue
            if pub_time.tzinfo is not None:
                pub_time = pub_time.replace(tzinfo=None)
            if pub_time >= cutoff:
                filtered.append(item)
        except (ValueError, TypeError):
            filtered.append(item)
    return filtered


def limit_per_source(results: List[Dict], max_per_source: Dict[str, int]) -> List[Dict]:
    """按数据源优先级排序后，按 maxResults 截取（每个源最多保留 maxResults 条）"""
    sorted_results = sorted(results, key=lambda x: SOURCE_PRIORITY.get(x.get("source", ""), 99))
    counters = {}
    filtered = []
    for item in sorted_results:
        source = item.get("source", "")
        limit = max_per_source.get(source, 0)
        if limit > 0 and counters.get(source, 0) < limit:
            filtered.append(item)
            counters[source] = counters.get(source, 0) + 1
    return filtered


# ==================== 主流程 ====================
async def main(config_path: str, output_path: str):
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    keywords = config.get("keywords", [])
    sources_config = config.get("sources", {})
    max_age_hours = config.get("maxAgeHours", 168)
    qf_config = config.get("qualityFilter", {})

    if not keywords:
        logger.error("No keywords provided")
        sys.exit(1)

    logger.info(f"Keywords: {keywords}")

    # 对每个数据源的 maxResults 做硬上限校验
    for src_name, src_conf in sources_config.items():
        if src_conf.get("enabled", False):
            cap = MAX_RESULTS_CAP.get(src_name, 10)
            user_val = src_conf.get("maxResults", cap)
            if user_val > cap:
                logger.warning(f"{src_name}: maxResults {user_val} exceeds cap {cap}, clamping")
                src_conf["maxResults"] = cap

    source_fetchers = {
        "bing": fetch_bing,
        "sogou": fetch_sogou,
        "bilibili": fetch_bilibili,
        "twitter": fetch_twitter,
        "youtube": fetch_youtube,
        "douyin": fetch_douyin,
    }

    # 构建抓取任务：每个关键词单独搜索，多个关键词并行
    # 每个关键词 × 每个已启用数据源 = 一个独立任务
    all_results = []
    tasks = []
    task_labels = []
    for keyword in keywords:
        for source_name, fetcher in source_fetchers.items():
            src_conf = sources_config.get(source_name, {})
            if not src_conf.get("enabled", False):
                continue
            tasks.append(fetcher(keyword, src_conf))
            task_labels.append((keyword, source_name))

    if not tasks:
        logger.error("No enabled sources")
        sys.exit(1)

    active_source_names = list(set(t[1] for t in task_labels))
    logger.info(f"Total tasks: {len(tasks)} ({len(keywords)} keywords × {len(active_source_names)} sources)")

    # 并行执行所有任务
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(results_list):
        if isinstance(result, Exception):
            logger.error(f"Task {task_labels[i][0]}@{task_labels[i][1]} error: {result}")
        elif isinstance(result, list):
            keyword = task_labels[i][0]
            for item in result:
                item["keyword"] = keyword
            all_results.extend(result)

    logger.info(f"Total raw results: {len(all_results)}")

    # 按关键词分组处理过滤
    keyword_results = {}
    for keyword in keywords:
        kw_items = [r for r in all_results if r.get("keyword") == keyword]

        unique = deduplicate_by_url(kw_items)
        quality = quality_filter(unique, qf_config)
        fresh = time_filter(quality, max_age_hours)

        # 按 maxResults 限制每个数据源的数量
        max_per_source = {}
        for src_name, src_conf in sources_config.items():
            if src_conf.get("enabled", False):
                max_per_source[src_name] = src_conf.get("maxResults", MAX_RESULTS_CAP.get(src_name, 10))

        final = limit_per_source(fresh, max_per_source)
        final.sort(key=lambda x: SOURCE_PRIORITY.get(x.get("source", ""), 99))

        keyword_results[keyword] = {
            "totalRaw": len(kw_items),
            "afterDedup": len(unique),
            "afterQuality": len(quality),
            "afterTimeFilter": len(fresh),
            "afterLimit": len(final),
            "results": final,
        }
        logger.info(f"Keyword '{keyword}': {len(kw_items)} raw -> {len(final)} final")

    # Write output
    total_raw = sum(v["totalRaw"] for v in keyword_results.values())
    total_final = sum(v["afterLimit"] for v in keyword_results.values())

    output = {
        "metadata": {
            "keywords": keywords,
            "sources": list(s for s, c in sources_config.items() if c.get("enabled")),
            "fetchTime": datetime.now().isoformat(),
            "totalRaw": total_raw,
            "totalFinal": total_final,
        },
        "keywordResults": keyword_results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"Results saved to {output_path}")
    print(f"\n{'='*50}")
    print(f"  HotRadar Fetch Complete")
    for kw, data in keyword_results.items():
        print(f"  [{kw}] Raw: {data['totalRaw']} -> Final: {data['afterLimit']}")
    print(f"  Total: {total_raw} raw -> {total_final} final")
    print(f"  Output: {output_path}")
    print(f"{'='*50}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <config.json> <output.json>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
