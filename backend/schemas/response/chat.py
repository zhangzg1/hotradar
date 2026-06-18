"""聊天响应体"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ChatResponse(BaseModel):
    """聊天响应"""
    reply: str = Field(..., description="AI回复内容")
    session_id: str = Field(..., description="会话ID")
    loaded_hotspots: Optional[List[str]] = Field(None, description="本轮加载的其他热点ID列表")


class ChatMessageResponse(BaseModel):
    """聊天消息响应"""
    id: str = Field(..., description="消息ID")
    role: str = Field(..., description="消息角色: user/assistant/tool")
    content: str = Field(..., description="消息内容")
    loaded_hotspots: Optional[List[str]] = Field(None, description="加载的其他热点ID")
    created_at: datetime = Field(..., description="创建时间")


class ChatSessionResponse(BaseModel):
    """聊天会话响应"""
    id: str = Field(..., description="会话ID")
    hotspot_id: str = Field(..., description="关联热点ID")
    name: Optional[str] = Field(None, description="会话名称")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    message_count: int = Field(0, description="消息数量")


class ChatSessionListResponse(BaseModel):
    """聊天会话列表响应"""
    data: List[ChatSessionResponse] = Field(default_factory=list, description="会话列表")
    total: int = Field(0, description="总数")