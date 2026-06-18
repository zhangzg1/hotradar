import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from backend.common.mysql import Base


class User(Base):
    """用户模型"""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), nullable=False, unique=True, comment="用户名")
    hashedPassword = Column("hashed_password", String(200), nullable=False, comment="密码哈希")
    createdAt = Column("created_at", DateTime, default=datetime.now, comment="创建时间")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"
