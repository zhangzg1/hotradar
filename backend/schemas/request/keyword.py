"""关键词请求体"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class BatchAction(str, Enum):
    """批量操作类型"""
    activate = "activate"
    deactivate = "deactivate"
    delete = "delete"


class KeywordCreateRequest(BaseModel):
    """创建关键词请求"""
    text: str = Field(..., min_length=1, max_length=100, description="关键词文本")
    category: Optional[str] = Field(None, max_length=50, description="分类")


class KeywordUpdateRequest(BaseModel):
    """更新关键词请求"""
    text: Optional[str] = Field(None, min_length=1, max_length=100, description="关键词文本")
    category: Optional[str] = Field(None, max_length=50, description="分类")


class KeywordBatchRequest(BaseModel):
    """批量操作请求"""
    action: BatchAction = Field(..., description="操作类型: activate/deactivate/delete")
    keywordIds: List[str] = Field(..., min_length=1, description="关键词ID列表")