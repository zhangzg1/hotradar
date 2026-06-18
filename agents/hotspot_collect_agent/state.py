"""
工作流状态定义
使用 TypedDict 定义工作流中传递的状态结构
"""
from typing import TypedDict, List, Optional, Dict, Any
from datetime import datetime


class AuthorInfo(TypedDict, total=False):
    """作者信息"""
    name: str
    username: Optional[str]
    avatar: Optional[str]
    followers: Optional[int]
    verified: Optional[bool]


class SearchResult(TypedDict, total=False):
    """搜索结果统一格式"""
    title: str                                    # 标题 (必填)
    content: str                                  # 内容摘要 (必填)
    url: str                                      # 链接 (必填)
    source: str                                   # 来源标识 (必填)
    sourceId: Optional[str]                       # 来源平台的唯一ID
    publishedAt: Optional[str]                    # 发布时间 (ISO格式)
    viewCount: Optional[int]                      # 浏览/播放量
    likeCount: Optional[int]                      # 点赞数
    retweetCount: Optional[int]                   # 转发数 (Twitter)
    replyCount: Optional[int]                     # 回复数
    quoteCount: Optional[int]                     # 引用数 (Twitter)
    score: Optional[int]                          # HN评分
    commentCount: Optional[int]                   # 评论数
    danmakuCount: Optional[int]                   # 弹幕数 (B站)
    author: Optional[AuthorInfo]                  # 作者信息


class AIAnalysis(TypedDict, total=False):
    """AI分析结果"""
    isReal: bool                                  # 真假识别
    relevance: int                                # 相关性评分 (0-100)
    relevanceReason: str                          # 相关性打分理由
    keywordMentioned: bool                        # 是否直接提及关键词
    importance: str                               # 重要程度 (low/medium/high/urgent)
    summary: str                                  # 与关键词的关联说明


class HotspotData(TypedDict, total=False):
    """热点完整数据 ( SearchResult + AIAnalysis )"""
    # SearchResult 字段
    title: str
    content: str
    url: str
    source: str
    sourceId: Optional[str]
    publishedAt: Optional[str]
    viewCount: Optional[int]
    likeCount: Optional[int]
    retweetCount: Optional[int]
    replyCount: Optional[int]
    quoteCount: Optional[int]
    score: Optional[int]
    commentCount: Optional[int]
    danmakuCount: Optional[int]
    author: Optional[AuthorInfo]
    # AIAnalysis 字段
    isReal: bool
    relevance: int
    relevanceReason: str
    keywordMentioned: bool
    importance: str
    summary: str
    # 元数据
    normalizedUrl: Optional[str]                  # 标准化后的URL
    inDatabase: Optional[bool]                    # 是否已存在于数据库


class WorkflowState(TypedDict, total=False):
    """工作流状态"""
    # 输入参数
    keyword: str                                  # 原始关键词
    keywordId: str                                # 关键词ID
    userId: str                                   # 用户ID
    fetchConfig: Dict[str, Any]                   # 抓取配置
    fetchQuotas: Dict[str, int]                   # 各数据源配额
    enabledSources: List[str]                     # 启用的数据源列表

    # 关键词扩展结果
    expandedKeywords: List[str]                   # 扩展后的关键词列表

    # 抓取阶段
    rawResults: List[SearchResult]                # 原始抓取结果 (所有数据源)

    # 去重清洗阶段
    uniqueResults: List[SearchResult]             # URL去重后结果
    qualityResults: List[SearchResult]            # 质量过滤后结果
    freshResults: List[SearchResult]              # 时间过滤后结果
    quotaFilteredResults: List[SearchResult]      # 配额截取后结果

    # AI分析阶段
    aiAnalysisResults: List[HotspotData]          # AI分析完成的热点数据

    # 最终结果
    savedHotspots: List[HotspotData]              # 已入库的热点数据
    savedCount: int                               # 入库数量
    filteredCount: int                            # 过滤数量

    # 错误处理
    errors: List[str]                             # 错误信息列表

    # 统计信息
    stats: Dict[str, Any]                         # 各阶段统计


class FetchStats(TypedDict, total=False):
    """抓取统计"""
    twitter_count: int
    youtube_count: int
    bilibili_count: int
    douyin_count: int
    bing_count: int
    sogou_count: int
    total_raw: int
    total_unique: int
    total_quality: int
    total_fresh: int
    total_quota: int
    total_ai_analyzed: int
    total_saved: int
    total_filtered: int