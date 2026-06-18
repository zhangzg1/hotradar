"""热点请求体"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class HotspotSearchRequest(BaseModel):
    """热点搜索请求"""
    query: str = Field(..., min_length=1, description="搜索关键词")
    keywordId: Optional[str] = Field(None, description="关键词ID筛选")
    source: Optional[str] = Field(None, description="来源筛选")
    importance: Optional[List[str]] = Field(None, description="重要程度筛选: low/medium/high/urgent")
    isReal: Optional[bool] = Field(None, description="真假筛选")
    publishedAtFrom: Optional[datetime] = Field(None, description="发布时间起始")
    publishedAtTo: Optional[datetime] = Field(None, description="发布时间结束")
    limit: int = Field(20, ge=1, le=100, description="返回数量限制")
    offset: int = Field(0, ge=0, description="偏移量")