# -*- coding: utf-8 -*-
"""
抖音关键词搜索模块 - 简化版
使用纯HTTP请求搜索抖音视频，无需签名JS文件（搜索API不需要a-bogus签名）

依赖：
    - httpx: 异步HTTP客户端
    - cookie.json: 登录后的cookie信息
"""
import json
import random
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx


class DouyinFetcher:
    """抖音关键词搜索器"""

    # Cookie文件路径（在同一目录下）
    COOKIE_FILE = Path(__file__).parent / "douyin_cookie.json"

    # 默认User-Agent
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

    def __init__(self, cookie: str = None, ms_token: str = None, user_id: str = None):
        """
        初始化搜索器

        Args:
            cookie: 抖音登录后的 cookie 字符串（可选，默认从数据库/文件读取）
            ms_token: 从 localStorage 获取的 xmst 值（可选）
            user_id: 用户ID（用于从数据库加载 Cookie）
        """
        self.cookie = cookie
        self.ms_token = ms_token or ""
        self._user_id = user_id
        self.host = "https://www.douyin.com"

        # 如果没有提供cookie，尝试从数据库或文件加载
        if not self.cookie:
            self._load_cookie()

    def _load_cookie(self) -> bool:
        """加载 Cookie：优先从数据库，回退到文件"""
        # 优先尝试从数据库加载（非异步环境降级到文件）
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在异步环境中无法同步等待，降级到文件
                return self._load_cookie_from_file()
            from backend.services.douyin_cookie_service import get_decrypted_cookie
            cookie_str, ms_token = loop.run_until_complete(get_decrypted_cookie(self._user_id))
            if cookie_str:
                self.cookie = cookie_str
                self.ms_token = ms_token
                return True
        except Exception:
            pass

        return self._load_cookie_from_file()

    def _load_cookie_from_file(self) -> bool:
        """从文件加载cookie"""
        try:
            if self.COOKIE_FILE.exists():
                with open(self.COOKIE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self.cookie = data.get("cookie_string", "")
                self.ms_token = data.get("ms_token", "")

                # 如果cookie_string为空，尝试从cookie_list构建
                if not self.cookie and data.get("cookie_list"):
                    self.cookie = "; ".join([
                        f"{c['name']}={c['value']}"
                        for c in data["cookie_list"]
                    ])

                return bool(self.cookie)
        except Exception:
            pass

        return False

    def _get_web_id(self) -> str:
        """生成随机webid"""
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

    def _build_common_params(self) -> Dict:
        """构建通用请求参数"""
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
            "webid": self._get_web_id(),
            "msToken": self.ms_token,
        }

    def _build_headers(self, keyword: str) -> Dict:
        """构建请求头"""
        return {
            "User-Agent": self.USER_AGENT,
            "Cookie": self.cookie,
            "Host": "www.douyin.com",
            "Origin": "https://www.douyin.com",
            "Referer": urllib.parse.quote(f"https://www.douyin.com/search/{keyword}", safe=':/'),
            "Content-Type": "application/json;charset=UTF-8",
        }

    async def search(
        self,
        keyword: str,
        max_count: int = 20,
        timeout: float = 30.0
    ) -> List[Dict]:
        """
        搜索抖音视频

        Args:
            keyword: 搜索关键词
            max_count: 最大返回数量
            timeout: 请求超时时间

        Returns:
            视频信息列表，包含 aweme_id, title, desc, url, author, statistics
        """
        if not self.cookie:
            return []

        results = []
        offset = 0
        search_id = ""
        headers = self._build_headers(keyword)

        async with httpx.AsyncClient(timeout=timeout) as client:
            while len(results) < max_count:
                # 构建搜索参数
                query_params = {
                    'search_channel': 'aweme_general',
                    'enable_history': '1',
                    'keyword': keyword,
                    'search_source': 'tab_search',
                    'query_correct_type': '1',
                    'is_filter_search': '0',
                    'offset': offset,
                    'count': '15',
                    'need_filter_settings': '1',
                    'list_type': 'multi',
                    'search_id': search_id,
                }

                # 合并通用参数
                query_params.update(self._build_common_params())

                # 搜索API不需要a-bogus签名
                uri = "/aweme/v1/web/general/search/single/"
                url = f"{self.host}{uri}"

                try:
                    response = await client.get(url, params=query_params, headers=headers)
                    data = response.json()

                    # 检查验证检查
                    nil_info = data.get("search_nil_info", {})
                    if nil_info.get("search_nil_type") == "verify_check":
                        # 触发验证，可能需要更新cookie
                        break

                    if not data.get("data"):
                        break

                    # 解析视频信息
                    for item in data.get("data", []):
                        aweme_info = item.get("aweme_info") or \
                            item.get("aweme_mix_info", {}).get("mix_items", [{}])[0]

                        if not aweme_info:
                            continue

                        aweme_id = aweme_info.get("aweme_id", "")
                        desc = aweme_info.get("desc", "")  # 抖音的desc就是标题/文案

                        # 获取作者信息
                        author_info = aweme_info.get("author", {})
                        author_name = author_info.get("nickname", "")
                        author_id = str(author_info.get("unique_id", "") or author_info.get("sec_uid", ""))

                        # 获取统计数据
                        statistics = aweme_info.get("statistics", {})

                        video_info = {
                            "aweme_id": aweme_id,
                            "title": desc[:100] if len(desc) > 100 else desc,
                            "desc": desc,  # 完整文案
                            "url": f"https://www.douyin.com/video/{aweme_id}",
                            "author": {
                                "name": author_name,
                                "username": author_id,
                            },
                            "viewCount": statistics.get("play_count", 0),
                            "likeCount": statistics.get("digg_count", 0),
                            "commentCount": statistics.get("comment_count", 0),
                            "shareCount": statistics.get("share_count", 0),
                            "publishedAt": aweme_info.get("create_time", 0),
                        }

                        results.append(video_info)

                        if len(results) >= max_count:
                            break

                    # 更新搜索参数
                    search_id = data.get("extra", {}).get("logid", "")
                    offset += 15

                    # 控制请求频率
                    import asyncio
                    await asyncio.sleep(random.uniform(1, 2))

                except (httpx.HTTPError, json.JSONDecodeError):
                    break

        return results[:max_count]


def load_cookie_from_file(cookie_file: str = None) -> Tuple[str, str]:
    """
    从cookie文件加载

    Args:
        cookie_file: cookie文件路径

    Returns:
        (cookie字符串, msToken)
    """
    if cookie_file is None:
        cookie_file = DouyinFetcher.COOKIE_FILE

    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        cookie_str = data.get("cookie_string", "")
        ms_token = data.get("ms_token", "")

        # 如果cookie_string为空，尝试从cookie_list构建
        if not cookie_str and data.get("cookie_list"):
            cookie_str = "; ".join([
                f"{c['name']}={c['value']}"
                for c in data["cookie_list"]
            ])

        return cookie_str, ms_token
    except Exception:
        return "", ""