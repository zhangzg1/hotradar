"""热点响应体"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class AuthorInfo(BaseModel):
    """作者信息"""
    name: Optional[str] = Field(None, description="作者名称")
    username: Optional[str] = Field(None, description="作者用户名")
    avatar: Optional[str] = Field(None, description="作者头像")
    followers: Optional[int] = Field(None, description="作者粉丝数")
    verified: Optional[bool] = Field(None, description="作者是否认证")


class EngagementStats(BaseModel):
    """互动统计"""
    viewCount: Optional[int] = Field(None, description="浏览数")
    likeCount: Optional[int] = Field(None, description="点赞数")
    retweetCount: Optional[int] = Field(None, description="转发数")
    replyCount: Optional[int] = Field(None, description="回复数")
    commentCount: Optional[int] = Field(None, description="评论数")
    quoteCount: Optional[int] = Field(None, description="引用数")
    danmakuCount: Optional[int] = Field(None, description="弹幕数")


class HotspotResponse(BaseModel):
    """热点基础响应"""
    id: str = Field(..., description="热点ID")
    title: str = Field(..., description="标题")
    content: str = Field(..., description="内容")
    url: str = Field(..., description="来源链接")
    source: str = Field(..., description="来源平台")
    isReal: bool = Field(True, description="是否真实")
    relevance: int = Field(0, description="相关性评分")
    importance: str = Field("low", description="重要程度: low/medium/high/urgent")
    summary: Optional[str] = Field(None, description="摘要")
    publishedAt: Optional[datetime] = Field(None, description="发布时间")
    createdAt: datetime = Field(..., description="创建时间")
    keywordId: Optional[str] = Field(None, description="关联关键词ID")


class HotspotDetailResponse(BaseModel):
    """热点详情响应"""
    id: str = Field(..., description="热点ID")
    title: str = Field(..., description="标题")
    content: str = Field(..., description="内容")
    url: str = Field(..., description="来源链接")
    source: str = Field(..., description="来源平台")
    sourceId: Optional[str] = Field(None, description="原始平台ID")
    isReal: bool = Field(True, description="是否真实")
    relevance: int = Field(0, description="相关性评分")
    relevanceReason: Optional[str] = Field(None, description="AI分析相关性理由")
    keywordMentioned: Optional[bool] = Field(None, description="是否直接提及关键词")
    importance: str = Field("low", description="重要程度")
    summary: Optional[str] = Field(None, description="摘要")
    author: AuthorInfo = Field(default_factory=AuthorInfo, description="作者信息")
    engagement: EngagementStats = Field(default_factory=EngagementStats, description="互动统计")
    emailSent: bool = Field(False, description="是否已邮件通知")
    emailSentAt: Optional[datetime] = Field(None, description="邮件发送时间")
    publishedAt: Optional[datetime] = Field(None, description="发布时间")
    createdAt: datetime = Field(..., description="创建时间")
    keywordId: Optional[str] = Field(None, description="关联关键词ID")


class HotspotListResponse(BaseModel):
    """热点列表响应"""
    data: List[HotspotResponse] = Field(default_factory=list, description="热点列表")
    total: int = Field(0, description="总数")
    page: int = Field(1, description="当前页码")
    pageSize: int = Field(20, description="每页数量")


class SourceDistribution(BaseModel):
    """来源分布"""
    source: str = Field(..., description="来源平台")
    count: int = Field(0, description="数量")


class ImportanceDistribution(BaseModel):
    """重要程度分布"""
    importance: str = Field(..., description="重要程度")
    count: int = Field(0, description="数量")


class HotspotStatsResponse(BaseModel):
    """热点统计响应"""
    total: int = Field(0, description="热点总数")
    todayNew: int = Field(0, description="今日新增数量")
    weekNew: int = Field(0, description="本周新增数量")
    importanceDistribution: List[ImportanceDistribution] = Field(
        default_factory=list, description="各重要程度数量"
    )
    sourceDistribution: List[SourceDistribution] = Field(
        default_factory=list, description="各来源分布"
    )
    realCount: int = Field(0, description="真实热点数量")
    fakeCount: int = Field(0, description="虚假热点数量")
    emailedCount: int = Field(0, description="已邮件通知数量")