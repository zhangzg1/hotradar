"""
热点采集工作流配置
"""
import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv(override=True)


# ==================== API Keys ====================
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")  # 兜底值，优先使用 app_settings 中的配置
TWITTER_API_BASE = "https://api.twitterapi.io"


# ==================== 数据源优先级 ====================
SOURCE_PRIORITY: Dict[str, int] = {
    "twitter": 1,       # 最高优先级
    "youtube": 2,       # 第二优先级
    "bilibili": 3,
    "douyin": 4,
    "bing": 5,
    "sogou": 6,
}


# ==================== 抓取配额（默认值，可被用户配置覆盖） ====================
DEFAULT_FETCH_QUOTAS: Dict[str, int] = {
    "twitter": 8,       # Twitter 配额
    "youtube": 8,       # YouTube 配额
    "bilibili": 3,      # Bilibili 配额
    "douyin": 3,        # 抖音 配额
    "bing": 2,          # Bing 配额
    "sogou": 1,         # 搜狗 配额
}

# 默认启用的数据源
DEFAULT_ENABLED_SOURCES: list = ["twitter", "youtube", "bilibili", "douyin", "bing", "sogou"]

# 向后兼容：旧版4桶配额（仅作 fallback）
FETCH_QUOTAS: Dict[str, int] = {
    "twitter": DEFAULT_FETCH_QUOTAS["twitter"],
    "youtube": DEFAULT_FETCH_QUOTAS["youtube"],
    "bilibili_douyin": DEFAULT_FETCH_QUOTAS["bilibili"] + DEFAULT_FETCH_QUOTAS["douyin"],
    "other": DEFAULT_FETCH_QUOTAS["bing"] + DEFAULT_FETCH_QUOTAS["sogou"],
}


# ==================== 时间过滤 ====================
MAX_AGE_HOURS = 168  # 7天


# ==================== 质量过滤规则 ====================
QUALITY_FILTER_RULES = {
    "min_title_length": 5,
    "min_content_length": 20,
}


# ==================== 三层过滤规则 ====================
FILTER_RULES: Dict[str, Any] = {
    "rule1": {"field": "isReal", "condition": "== true"},
    "rule2": {"field": "relevance", "condition": ">= 50"},
    "rule3": {"field": "keywordMentioned", "condition": "== true OR relevance >= 65"},
}


# ==================== 抓取配置 ====================
DEFAULT_FETCH_CONFIG: Dict[str, Any] = {
    "twitter": {
        "maxResults": 20,
        "strategy": "Top(2页) + Latest(1页)",
        "qualityFilter": {
            "minLikes": 10,
            "minRetweets": 5,
            "minViews": 500,
            "minFollowers": 100,
        },
    },
    "youtube": {"maxResults": 20, "order": "relevance"},
    "bilibili": {"maxResults": 20, "orderBy": "pubdate"},
    "douyin": {"maxResults": 20},
    "bing": {"maxResults": 10},
    "sogou": {"maxResults": 10},
}


# ==================== 频率限制 (毫秒) ====================
RATE_LIMITS: Dict[str, int] = {
    "twitter": 0,       # 无限制 (付费API)
    "youtube": 1000,    # 1秒 (API Key 模式，适度控制)
    "bing": 5000,       # 5秒
    "sogou": 3000,      # 3秒
    "bilibili": 2000,   # 2秒
    "douyin": 3000,     # 3秒
}


# ==================== User-Agent 池 ====================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


# ==================== AI 分析配置 ====================
AI_CONFIG = {
    "model": "deepseek-chat",       # 使用的模型
    "temperature": 0.2,             # 低温度提高一致性
    "max_tokens": 500,              # 最大输出长度
    "content_max_length": 2000,     # 内容截断长度
}


# ==================== 关键词扩展配置 ====================
KEYWORD_EXPANSION_CONFIG = {
    "model": "deepseek-chat",
    "temperature": 0.3,
    "max_variants": 15,             # 最大变体数量
    "min_variants": 5,              # 最小变体数量
}


# ==================== 重要程度映射 ====================
IMPORTANCE_LEVELS = ["low", "medium", "high", "urgent"]
IMPORTANCE_WEIGHTS = {
    "urgent": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}