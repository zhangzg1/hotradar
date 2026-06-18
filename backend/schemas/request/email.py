"""邮件通知请求体"""
from pydantic import BaseModel, Field
from typing import Optional, List


class EmailNotificationRequest(BaseModel):
    """邮件通知请求"""
    hours: Optional[int] = Field(24, ge=1, le=168, description="时间范围（小时）")
    importance: Optional[List[str]] = Field(
        ["high", "urgent"], description="级别筛选"
    )
    keywordIds: Optional[List[str]] = Field(None, description="关键词ID筛选")