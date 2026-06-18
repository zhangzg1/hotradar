"""采集任务请求体"""
from pydantic import BaseModel, Field
from typing import List


class CollectionRequest(BaseModel):
    """采集任务请求"""
    keywordIds: List[str] = Field(..., description="关键词ID列表")