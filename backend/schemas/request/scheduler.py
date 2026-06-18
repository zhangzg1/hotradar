"""调度配置请求体"""
from pydantic import BaseModel, Field


class SchedulerConfigRequest(BaseModel):
    """调度配置更新请求"""
    isEnabled: bool = Field(..., description="是否启用定时调度")
    intervalHours: int = Field(2, ge=1, le=72, description="调度间隔（小时）")
