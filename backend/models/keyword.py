from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.orm import relationship
from backend.common.mysql import Base


class Keyword(Base):
    """关键词模型"""

    __tablename__ = "keywords"

    id = Column(String(36), primary_key=True)
    userId = Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户 ID")
    text = Column(String(100), nullable=False, comment="关键词文本")
    category = Column(String(50), nullable=True, comment="分类")
    isActive = Column(Boolean, default=True, comment="是否激活")
    createdAt = Column(DateTime, default=datetime.now, comment="创建时间")
    updatedAt = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    hotspots = relationship("Hotspot", back_populates="keyword", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("text", "user_id", name="uq_keyword_text_user"),)

    def __repr__(self):
        return f"<Keyword(id={self.id}, text={self.text})>"