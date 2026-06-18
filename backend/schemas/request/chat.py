"""聊天请求体"""
from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., min_length=1, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID，不传则创建新会话")