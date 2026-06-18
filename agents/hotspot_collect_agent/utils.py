"""
辅助函数
包含URL标准化、去重、过滤、关键词预匹配等功能
"""
import re
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from .state import SearchResult
from .config import (
    QUALITY_FILTER_RULES,
    MAX_AGE_HOURS,
    SOURCE_PRIORITY,
    DEFAULT_FETCH_QUOTAS,
    FETCH_QUOTAS,
    USER_AGENTS,
    IMPORTANCE_LEVELS,
)


# ==================== URL处理 ====================
def normalize_url(url: str) -> str:
    """
    URL标准化处理

    Args:
        url: 原始URL

    Returns:
        标准化后的URL
    """
    if not url:
        return ""

    normalized = url.strip()

    # 移除末尾斜杠
    normalized = normalized.rstrip("/")

    # 移除 www. 前缀
    normalized = re.sub(r"^https?://www\.", "https://", normalized)

    # 统一为 https
    normalized = re.sub(r"^http://", "https://", normalized)

    return normalized


def parse_datetime(date_str: str) -> Optional[datetime]:
    """
    解析多种日期格式

    支持格式:
    - ISO格式: 2026-04-18T10:00:00+00:00
    - Twitter格式: Sun Apr 12 07:40:34 +0000 2026
    - B站格式: 2026-04-18 10:00:00

    Args:
        date_str: 日期字符串

    Returns:
        datetime对象或None
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # 尝试ISO格式
    try:
        # 处理Z后缀
        if date_str.endswith("Z"):
            date_str = date_str[:-1] + "+00:00"
        return datetime.fromisoformat(date_str)
    except ValueError:
        pass

    # 尝试Twitter格式: Sun Apr 12 07:40:34 +0000 2026
    try:
        from datetime import timezone
        # 解析Twitter时间格式
        import email.utils
        parsed = email.utils.parsedate_to_datetime(date_str)
        return parsed
    except Exception:
        pass

    # 尝试B站格式: 2026-04-18 10:00:00
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass

    # 尝试其他常见格式
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def get_random_user_agent() -> str:
    """
    获取随机 User-Agent

    Returns:
        随机选择的 User-Agent 字符串
    """
    return random.choice(USER_AGENTS)


# ==================== 去重 ====================
def deduplicate_by_url(results: List[SearchResult]) -> List[SearchResult]:
    """
    URL去重

    Args:
        results: 搜索结果列表

    Returns:
        去重后的结果列表
    """
    unique_urls: Dict[str, SearchResult] = {}

    for item in results:
        normalized_url = normalize_url(item.get("url", ""))

        if not normalized_url:
            continue

        # 如果URL已存在，检查优先级
        if normalized_url in unique_urls:
            existing = unique_urls[normalized_url]
            existing_priority = SOURCE_PRIORITY.get(existing.get("source", ""), 99)
            new_priority = SOURCE_PRIORITY.get(item.get("source", ""), 99)

            # 保留优先级更高的
            if new_priority < existing_priority:
                unique_urls[normalized_url] = item
        else:
            unique_urls[normalized_url] = item

    return list(unique_urls.values())


# ==================== 质量过滤 ====================
def quality_filter(results: List[SearchResult]) -> List[SearchResult]:
    """
    质量过滤

    过滤规则:
    1. title 为空或长度小于 5
    2. content 为空或长度小于 20
    3. URL 非法 (不以 http 开头)

    Args:
        results: 搜索结果列表

    Returns:
        过滤后的结果列表
    """
    filtered = []

    for item in results:
        title = item.get("title", "")
        content = item.get("content", "")
        url = item.get("url", "")

        # 检查标题
        if not title or len(title.strip()) < QUALITY_FILTER_RULES["min_title_length"]:
            continue

        # 检查内容
        if not content or len(content.strip()) < QUALITY_FILTER_RULES["min_content_length"]:
            continue

        # 检查URL
        if not url or not url.startswith("http"):
            continue

        filtered.append(item)

    return filtered


# ==================== 时间过滤 ====================
def time_filter(results: List[SearchResult], max_hours: int = MAX_AGE_HOURS) -> List[SearchResult]:
    """
    时间过滤（新鲜度过滤）

    Args:
        results: 搜索结果列表
        max_hours: 最大保留时间（小时）

    Returns:
        过滤后的结果列表
    """
    cutoff_time = datetime.now() - timedelta(hours=max_hours)
    filtered = []

    for item in results:
        published_at = item.get("publishedAt")

        # 没有发布时间的，暂时保留
        if not published_at:
            filtered.append(item)
            continue

        # 解析时间
        try:
            if isinstance(published_at, str):
                pub_time = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            elif isinstance(published_at, datetime):
                pub_time = published_at
            else:
                # 无法解析，保留
                filtered.append(item)
                continue

            # 检查是否在时间范围内
            # 处理时区问题：如果 pub_time 有时区信息，需要转换为本地时间比较
            if pub_time.tzinfo is not None:
                # 转换为无时区的本地时间
                pub_time = pub_time.replace(tzinfo=None)

            if pub_time >= cutoff_time:
                filtered.append(item)

        except (ValueError, TypeError):
            # 解析失败，保留
            filtered.append(item)

    return filtered


# ==================== 配额截取 ====================
def quota_cutoff(
    results: List[SearchResult],
    quotas: Optional[Dict[str, int]] = None,
    priority_map: Dict[str, int] = SOURCE_PRIORITY,
) -> List[SearchResult]:
    """
    配额截取

    支持两种配额格式:
    1. 6个独立配额: {"twitter": 8, "youtube": 8, "bilibili": 3, "douyin": 3, "bing": 2, "sogou": 1}
    2. 4个共享配额(旧版): {"twitter": 8, "youtube": 8, "bilibili_douyin": 6, "other": 3}

    Args:
        results: 搜索结果列表（已按优先级排序）
        quotas: 配额配置，默认使用 DEFAULT_FETCH_QUOTAS
        priority_map: 优先级映射

    Returns:
        截取后的结果列表
    """
    if quotas is None:
        quotas = DEFAULT_FETCH_QUOTAS

    # 先按优先级排序
    sorted_results = sort_by_priority(results, priority_map)

    # 判断是6独立配额还是4共享配额
    has_individual_quotas = "bilibili" in quotas and "douyin" in quotas

    # 计数器
    counters: Dict[str, int] = {}

    filtered = []

    for item in sorted_results:
        source = item.get("source", "")

        if has_individual_quotas:
            # 6个独立配额模式
            quota_key = source
            if quota_key not in quotas:
                quota_key = "sogou"  # 未知来源使用最低配额
            if counters.get(source, 0) < quotas.get(quota_key, 0):
                filtered.append(item)
                counters[source] = counters.get(source, 0) + 1
        else:
            # 4个共享配额模式（向后兼容）
            twitter_quota = quotas.get("twitter", 8)
            youtube_quota = quotas.get("youtube", 8)
            bilibili_douyin_quota = quotas.get("bilibili_douyin", 6)
            other_quota = quotas.get("other", 3)

            if source == "twitter":
                if counters.get("twitter", 0) < twitter_quota:
                    filtered.append(item)
                    counters["twitter"] = counters.get("twitter", 0) + 1
            elif source == "youtube":
                if counters.get("youtube", 0) < youtube_quota:
                    filtered.append(item)
                    counters["youtube"] = counters.get("youtube", 0) + 1
            elif source in ["bilibili", "douyin"]:
                if counters.get("bilibili_douyin", 0) < bilibili_douyin_quota:
                    filtered.append(item)
                    counters["bilibili_douyin"] = counters.get("bilibili_douyin", 0) + 1
            else:
                if counters.get("other", 0) < other_quota:
                    filtered.append(item)
                    counters["other"] = counters.get("other", 0) + 1

    return filtered


def sort_by_priority(
    results: List[SearchResult],
    priority_map: Dict[str, int] = SOURCE_PRIORITY,
) -> List[SearchResult]:
    """
    按数据源优先级排序

    Args:
        results: 搜索结果列表
        priority_map: 优先级映射

    Returns:
        排序后的结果列表
    """
    return sorted(
        results,
        key=lambda x: priority_map.get(x.get("source", ""), 99),
    )


# ==================== Twitter质量评分 ====================
def calculate_twitter_score(tweet: SearchResult) -> int:
    """
    计算 Twitter 质量评分

    公式: likes * 2 + retweets * 3 + views / 100 + 蓝V加权

    Args:
        tweet: Twitter 搜索结果

    Returns:
        质量评分
    """
    likes = tweet.get("likeCount", 0) or 0
    retweets = tweet.get("retweetCount", 0) or 0
    views = tweet.get("viewCount", 0) or 0

    # 基础分数
    score = likes * 2 + retweets * 3 + views // 100

    # 蓝V加权
    author = tweet.get("author", {})
    if author and author.get("verified", False):
        score += 50

    return score


def sort_twitter_by_quality(tweets: List[SearchResult]) -> List[SearchResult]:
    """
    按质量评分排序 Twitter 结果

    Args:
        tweets: Twitter 搜索结果列表

    Returns:
        排序后的结果列表
    """
    return sorted(tweets, key=calculate_twitter_score, reverse=True)


# ==================== 关键词预匹配 ====================
def pre_match_keyword(text: str, expanded_keywords: List[str]) -> Dict[str, Any]:
    """
    关键词预匹配

    在调用 AI 分析前，先检查文本是否包含任一扩展关键词

    Args:
        text: 待检查的文本
        expanded_keywords: 扩展后的关键词列表

    Returns:
        {"matched": bool, "matchedTerms": list}
    """
    lower_text = text.lower()
    matched_terms = []

    for kw in expanded_keywords:
        if lower_text.find(kw.lower()) != -1:
            matched_terms.append(kw)

    return {
        "matched": len(matched_terms) > 0,
        "matchedTerms": matched_terms,
    }


# ==================== 三层过滤 ====================
def apply_three_layer_filter(analysis: Dict[str, Any], filter_rules: Dict[str, Any]) -> bool:
    """
    应用三层过滤规则

    Args:
        analysis: AI 分析结果
        filter_rules: 过滤规则

    Returns:
        是否通过过滤
    """
    # 第一层: 真假过滤
    is_real = analysis.get("isReal", True)
    if not is_real:
        return False

    # 第二层: 相关性阈值
    relevance = analysis.get("relevance", 0)
    if relevance < 50:
        return False

    # 第三层: 关键词提及组合过滤
    keyword_mentioned = analysis.get("keywordMentioned", False)
    if not keyword_mentioned and relevance < 65:
        return False

    return True


# ==================== 核心词提取 (纯文本方式) ====================
def extract_core_terms(keyword: str) -> List[str]:
    """
    纯文本方式提取核心词

    分割规则: 空格、连字符、下划线、斜杠、反斜杠、中文点号

    Args:
        keyword: 原始关键词

    Returns:
        核心词列表
    """
    # 分割
    parts = re.split(r"[\s\-_\/\\·]+", keyword)
    parts = [p.strip() for p in parts if len(p.strip()) >= 2]

    # 组合相邻词
    combined = []
    for i in range(len(parts)):
        combined.append(parts[i])
        if i < len(parts) - 1:
            combined.append(f"{parts[i]} {parts[i+1]}")

    return list(set(combined))


# ==================== JSON解析辅助 ====================
def parse_json_from_text(text: str) -> Optional[Any]:
    """
    从文本中提取JSON

    Args:
        text: 包含JSON的文本

    Returns:
        解析后的JSON对象，或 None
    """
    try:
        # 尝试匹配 JSON 数组或对象
        json_match = re.search(r"(\[[\s\S]*\]|\{[\s\S]*\})", text)
        if json_match:
            import json
            return json.loads(json_match.group(1))
        return None
    except (json.JSONDecodeError, ValueError):
        return None


# ==================== 日期格式化 ====================
def format_since_date(days: int) -> str:
    """
    格式化 Twitter 搜索的 since 日期

    Args:
        days: 天数

    Returns:
        格式化后的日期字符串 (YYYY-MM-DD)
    """
    date = datetime.now() - timedelta(days=days)
    return date.strftime("%Y-%m-%d")


# ==================== 结果统计 ====================
def count_by_source(results: List[SearchResult]) -> Dict[str, int]:
    """
    统计各数据源的结果数量

    Args:
        results: 搜索结果列表

    Returns:
        各数据源的计数 {"twitter": 10, "bing": 5, ...}
    """
    counts: Dict[str, int] = {}
    for item in results:
        source = item.get("source", "unknown")
        counts[source] = counts.get(source, 0) + 1
    return counts


# ==================== 验证重要程度 ====================
def validate_importance(importance: str) -> str:
    """
    验证重要程度值

    Args:
        importance: 重要程度值

    Returns:
        有效的重要程度值 (默认 "low")
    """
    if importance in IMPORTANCE_LEVELS:
        return importance
    return "low"