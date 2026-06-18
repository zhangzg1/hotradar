"""邮件通知响应体"""
from pydantic import BaseModel, Field
from typing import List, Any


class EmailNotificationResponse(BaseModel):
    """邮件通知响应"""
    sentCount: int = Field(..., description="发送数量")
    hotspots: List[Any] = Field(default_factory=list, description="发送的热点列表")
    message: str = Field("邮件已发送", description="提示消息")