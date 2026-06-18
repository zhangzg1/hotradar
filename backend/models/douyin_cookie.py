import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from backend.common.mysql import Base


class DouyinCookie(Base):
    """抖音登录 Cookie 模型"""

    __tablename__ = "douyin_cookies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    userId = Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户 ID")
    cookieString = Column("cookie_string", Text, nullable=True, comment="完整 Cookie 字符串（加密）")
    msToken = Column("ms_token", String(500), nullable=True, comment="msToken（加密）")
    status = Column(String(20), nullable=False, default="active", comment="Cookie 状态: active / expired")
    expiresAt = Column("expires_at", DateTime, nullable=True, comment="预计过期时间")
    createdAt = Column("created_at", DateTime, default=datetime.now, comment="创建时间")
    updatedAt = Column("updated_at", DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<DouyinCookie(user={self.userId}, status={self.status})>"
