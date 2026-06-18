from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey
from backend.common.mysql import Base


class SchedulerConfig(Base):
    """定时调度配置模型"""

    __tablename__ = "scheduler_config"

    id = Column(String(36), primary_key=True)
    userId = Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户 ID")
    intervalHours = Column("interval_hours", Integer, nullable=False, default=2, comment="调度间隔（小时）")
    isEnabled = Column("is_enabled", Boolean, nullable=False, default=False, comment="是否启用")
    lastRunAt = Column("last_run_at", DateTime, nullable=True, comment="上次执行时间")
    lastRunStatus = Column("last_run_status", String(20), nullable=True, comment="上次执行状态")
    nextRunAt = Column("next_run_at", DateTime, nullable=True, comment="下次执行时间")
    updatedAt = Column("updated_at", DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<SchedulerConfig(id={self.id}, interval={self.intervalHours}h, enabled={self.isEnabled})>"
