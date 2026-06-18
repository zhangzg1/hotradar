from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from backend.common.mysql import Base


class AppSettings(Base):
    """应用全局设置模型"""

    __tablename__ = "app_settings"

    id = Column(String(36), primary_key=True)
    userId = Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户 ID")
    llmBaseUrl = Column("llm_base_url", String(500), nullable=True, comment="LLM Base URL")
    llmApiKey = Column("llm_api_key", String(500), nullable=True, comment="LLM API Key (加密)")
    llmModelName = Column("llm_model_name", String(100), nullable=True, comment="LLM 模型名称")
    llmTested = Column("llm_tested", Boolean, nullable=False, default=False, comment="LLM 是否测试通过")
    notifyEmail = Column("notify_email", String(200), nullable=True, comment="收件邮箱")
    twitterApiKey = Column("twitter_api_key", String(500), nullable=True, comment="Twitter API Key (加密)")
    twitterTested = Column("twitter_tested", Boolean, nullable=False, default=False, comment="Twitter API 是否测试通过")
    createdAt = Column("created_at", DateTime, default=datetime.now, comment="创建时间")
    updatedAt = Column("updated_at", DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return (f"<AppSettings(llm={self.llmBaseUrl}/{self.llmModelName}/{self.llmTested}, "
                f"email={self.notifyEmail}, twitter={self.twitterTested})>")
