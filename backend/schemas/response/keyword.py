"""关键词响应体"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class KeywordResponse(BaseModel):
    """关键词基础响应"""
    id: str = Field(..., description="关键词ID")
    text: str = Field(..., description="关键词文本")
    category: Optional[str] = Field(None, description="分类")
    isActive: bool = Field(True, description="是否激活")
    createdAt: datetime = Field(..., description="创建时间")
    updatedAt: datetime = Field(..., description="更新时间")


class KeywordDetailResponse(BaseModel):
    """关键词详情响应（含热点统计）"""
    id: str = Field(..., description="关键词ID")
    text: str = Field(..., description="关键词文本")
    category: Optional[str] = Field(None, description="分类")
    isActive: bool = Field(True, description="是否激活")
    createdAt: datetime = Field(..., description="创建时间")
    updatedAt: datetime = Field(..., description="更新时间")
    hotspotCount: int = Field(0, description="关联热点数量")
    recentHotspots: List[Any] = Field(default_factory=list, description="最近热点列表")


class KeywordListResponse(BaseModel):
    """关键词列表响应"""
    data: List[KeywordDetailResponse] = Field(default_factory=list, description="关键词列表")
    total: int = Field(0, description="总数")
    page: int = Field(1, description="当前页码")
    pageSize: int = Field(20, description="每页数量")


class CategoryStats(BaseModel):
    """分类统计"""
    category: Optional[str] = Field(None, description="分类名称")
    count: int = Field(0, description="数量")


class KeywordStatsResponse(BaseModel):
    """关键词统计响应"""
    total: int = Field(0, description="关键词总数")
    active: int = Field(0, description="活跃关键词数量")
    inactive: int = Field(0, description="暂停关键词数量")
    categories: List[CategoryStats] = Field(default_factory=list, description="各分类数量统计")