from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, UniqueConstraint, ForeignKey
from sqlalchemy.orm import relationship
from backend.common.mysql import Base


class Hotspot(Base):
    """热点数据模型"""

    __tablename__ = "hotspots"

    id = Column(String(36), primary_key=True)
    userId = Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户 ID")
    title = Column(String(500), nullable=False, comment="标题")
    content = Column(Text, nullable=False, comment="内容")
    fullContent = Column(Text, nullable=True, comment="完整原文内容（含字幕）")
    url = Column(String(255), nullable=False, comment="来源链接")
    source = Column(String(50), nullable=False, comment="来源平台")
    sourceId = Column(String(100), nullable=True, comment="原始平台ID")

    isReal = Column(Boolean, default=True, comment="是否真实")
    relevance = Column(Integer, default=0, comment="相关性评分 0-100")
    relevanceReason = Column(Text, nullable=True, comment="AI分析相关性理由")
    keywordMentioned = Column(Boolean, nullable=True, comment="是否直接提及关键词")
    importance = Column(String(20), default="low", comment="重要程度: low/medium/high")
    summary = Column(Text, nullable=True, comment="摘要")

    viewCount = Column(Integer, nullable=True, comment="浏览数")
    likeCount = Column(Integer, nullable=True, comment="点赞数")
    retweetCount = Column(Integer, nullable=True, comment="转发数")
    replyCount = Column(Integer, nullable=True, comment="回复数")
    commentCount = Column(Integer, nullable=True, comment="评论数")
    quoteCount = Column(Integer, nullable=True, comment="引用/转引数")
    danmakuCount = Column(Integer, nullable=True, comment="弹幕数")

    authorName = Column(String(200), nullable=True, comment="作者名称")
    authorUsername = Column(String(100), nullable=True, comment="作者用户名")
    authorAvatar = Column(String(255), nullable=True, comment="作者头像")
    authorFollowers = Column(Integer, nullable=True, comment="作者粉丝数")
    authorVerified = Column(Boolean, nullable=True, comment="作者是否认证")

    emailSent = Column(Boolean, default=False, comment="是否已邮件通知")
    emailSentAt = Column(DateTime, nullable=True, comment="邮件发送时间")

    publishedAt = Column(DateTime, nullable=True, comment="发布时间")
    createdAt = Column(DateTime, default=datetime.now, comment="创建时间")

    keywordId = Column(String(36), ForeignKey("keywords.id", ondelete="CASCADE"), nullable=True, comment="关联关键词ID")
    keyword = relationship("Keyword", back_populates="hotspots")

    # 级联删除聊天会话
    chatSessions = relationship("ChatSession", back_populates="hotspot", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("url", "source", name="uq_hotspot_url_source"),)

    def __repr__(self):
        return f"<Hotspot(id={self.id}, title={self.title[:30]}..., source={self.source})>"