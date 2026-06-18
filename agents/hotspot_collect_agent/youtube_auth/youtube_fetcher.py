# -*- coding: utf-8 -*-
"""
YouTube关键词搜索模块
使用 YouTube Data API v3 搜索视频，返回结构化数据

依赖：
    - httpx: 异步HTTP客户端
    - YOUTUBE_API_KEY: YouTube Data API v3 密钥（存储在 .env 中）

参考模式：Bilibili 公开 API + Douyin 认证搜索
"""
import os
import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import httpx
from dotenv import load_dotenv

load_dotenv(override=True)


class YouTubeFetcher:
    """YouTube关键词搜索器"""

    API_BASE = "https://www.googleapis.com/youtube/v3"

    # 默认User-Agent
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )

    def __init__(self, api_key: str = None):
        """
        初始化搜索器

        Args:
            api_key: YouTube Data API v3 密钥（可选，默认从环境变量读取）
        """
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY", "")

    @property
    def available(self) -> bool:
        """检查 API Key 是否已配置"""
        return bool(self.api_key)

    def _build_search_params(
        self,
        keyword: str,
        max_results: int = 20,
        page_token: str = None,
        order: str = "relevance",
        published_after: str = None,
    ) -> Dict:
        """
        构建搜索请求参数

        Args:
            keyword: 搜索关键词
            max_results: 单页最大结果数 (1-50)
            page_token: 分页令牌
            order: 排序方式 (relevance/date/rating/viewCount)
            published_after: ISO 8601 格式的最早发布时间
        """
        params = {
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "maxResults": min(max_results, 50),
            "order": order,
            "videoDefinition": "any",
            "key": self.api_key,
        }

        if page_token:
            params["pageToken"] = page_token

        if published_after:
            params["publishedAfter"] = published_after

        return params

    def _build_video_stats_params(self, video_ids: List[str]) -> Dict:
        """
        构建视频统计信息请求参数

        Args:
            video_ids: 视频ID列表
        """
        return {
            "part": "statistics,contentDetails",
            "id": ",".join(video_ids),
            "key": self.api_key,
        }

    def _build_headers(self) -> Dict:
        """构建请求头"""
        return {
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json",
        }

    def _parse_duration(self, duration: str) -> int:
        """
        解析 ISO 8601 时长格式为秒数

        格式: PT1H2M10S -> 3730秒

        Args:
            duration: ISO 8601 时长字符串

        Returns:
            时长秒数
        """
        if not duration:
            return 0

        import re
        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
        if not match:
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds

    async def search(
        self,
        keyword: str,
        max_count: int = 20,
        order: str = "relevance",
        days: int = 7,
        timeout: float = 30.0,
    ) -> List[Dict]:
        """
        搜索YouTube视频

        分两步执行：
        1. 使用 search 端点获取视频基本信息（标题、描述、频道、发布时间）
        2. 使用 videos 端点获取视频统计信息（播放量、点赞数、评论数）

        Args:
            keyword: 搜索关键词
            max_count: 最大返回数量
            order: 排序方式 (relevance/date/rating/viewCount)
            days: 搜索最近N天内的视频
            timeout: 请求超时时间

        Returns:
            视频信息列表，包含 video_id, title, desc, url, author, statistics
        """
        if not self.api_key:
            return []

        results = []
        page_token = None

        # 计算时间过滤范围
        from datetime import datetime, timedelta, timezone
        published_after = (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).isoformat()

        async with httpx.AsyncClient(timeout=timeout) as client:
            while len(results) < max_count:
                # Step 1: 搜索视频
                search_params = self._build_search_params(
                    keyword=keyword,
                    max_results=min(50, max_count - len(results)),
                    page_token=page_token,
                    order=order,
                    published_after=published_after,
                )

                try:
                    response = await client.get(
                        f"{self.API_BASE}/search",
                        params=search_params,
                        headers=self._build_headers(),
                    )
                    data = response.json()

                    # 检查API错误
                    if "error" in data:
                        error_msg = data["error"].get("message", "Unknown error")
                        print(f"YouTube API 错误: {error_msg}")
                        break

                    items = data.get("items", [])
                    if not items:
                        break

                    # 收集视频ID，用于批量获取统计信息
                    video_ids = []
                    search_results = []

                    for item in items:
                        video_id = item.get("id", {}).get("videoId", "")
                        if not video_id:
                            continue

                        snippet = item.get("snippet", {})

                        video_info = {
                            "video_id": video_id,
                            "title": snippet.get("title", ""),
                            "desc": snippet.get("description", ""),
                            "url": f"https://www.youtube.com/watch?v={video_id}",
                            "publishedAt": snippet.get("publishedAt", ""),
                            "thumbnail": (
                                snippet.get("thumbnails", {})
                                .get("high", {})
                                .get("url", "")
                            ),
                            "author": {
                                "name": snippet.get("channelTitle", ""),
                                "username": snippet.get("channelId", ""),
                                "channel_url": (
                                    f"https://www.youtube.com/channel/{snippet.get('channelId', '')}"
                                ),
                            },
                        }

                        video_ids.append(video_id)
                        search_results.append(video_info)

                    # Step 2: 批量获取视频统计信息
                    if video_ids:
                        stats_params = self._build_video_stats_params(video_ids)
                        try:
                            stats_response = await client.get(
                                f"{self.API_BASE}/videos",
                                params=stats_params,
                                headers=self._build_headers(),
                            )
                            stats_data = stats_response.json()

                            # 构建统计信息映射
                            stats_map = {}
                            for stat_item in stats_data.get("items", []):
                                vid = stat_item.get("id", "")
                                statistics = stat_item.get("statistics", {})
                                content_details = stat_item.get("contentDetails", {})
                                stats_map[vid] = {
                                    "statistics": statistics,
                                    "duration": self._parse_duration(
                                        content_details.get("duration", "")
                                    ),
                                }
                        except (httpx.HTTPError, json.JSONDecodeError):
                            stats_map = {}

                        # 合并统计信息到搜索结果
                        for video_info in search_results:
                            vid = video_info["video_id"]
                            if vid in stats_map:
                                stats = stats_map[vid]["statistics"]
                                video_info["viewCount"] = int(
                                    stats.get("viewCount", 0)
                                )
                                video_info["likeCount"] = int(
                                    stats.get("likeCount", 0)
                                )
                                video_info["commentCount"] = int(
                                    stats.get("commentCount", 0)
                                )
                                video_info["duration"] = stats_map[vid]["duration"]
                            else:
                                video_info["viewCount"] = 0
                                video_info["likeCount"] = 0
                                video_info["commentCount"] = 0
                                video_info["duration"] = 0

                            results.append(video_info)

                    # 检查是否还有下一页
                    page_token = data.get("nextPageToken")
                    if not page_token:
                        break

                    # 控制请求频率
                    import asyncio
                    await asyncio.sleep(random.uniform(0.5, 1.5))

                except (httpx.HTTPError, json.JSONDecodeError) as e:
                    print(f"YouTube 请求失败: {e}")
                    break

        return results[:max_count]


def load_api_key_from_env() -> str:
    """
    从环境变量加载YouTube API Key

    Returns:
        API Key字符串
    """
    return os.getenv("YOUTUBE_API_KEY", "")
