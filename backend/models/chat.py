"""
聊天会话和消息模型
用于热点问答功能的多轮对话会话管理
"""
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.common.mysql import Base


class ChatSession(Base):
    """聊天会话模型"""

    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True)
    userId = Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户 ID")
    hotspotId = Column(String(36), ForeignKey("hotspots.id", ondelete="CASCADE"), nullable=False, comment="关联热点ID")
    name = Column(String(100), nullable=True, comment="会话名称")
    createdAt = Column(DateTime, default=datetime.now, comment="创建时间")
    updatedAt = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关联热点
    hotspot = relationship("Hotspot", back_populates="chatSessions")

    # 级联删除消息
    messages = relationship("ChatMessage", back_populates="session", order_by="ChatMessage.createdAt", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatSession(id={self.id}, hotspotId={self.hotspotId})>"


class ChatMessage(Base):
    """聊天消息模型"""

    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True)
    sessionId = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, comment="关联会话ID")
    role = Column(String(20), nullable=False, comment="消息角色: user/assistant/tool")
    content = Column(Text, nullable=False, comment="消息内容")
    loadedHotspots = Column(Text, nullable=True, comment="本轮加载的其他热点ID列表(JSON格式)")
    createdAt = Column(DateTime, default=datetime.now, comment="创建时间")

    session = relationship("ChatSession", back_populates="messages")

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, role={self.role})>"