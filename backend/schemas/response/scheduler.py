"""调度配置响应体"""
from typing import Optional
from pydantic import BaseModel, Field


class SchedulerConfigResponse(BaseModel):
    """调度配置响应"""
    isEnabled: bool = Field(..., description="是否启用")
    intervalHours: int = Field(..., description="调度间隔（小时）")


class SchedulerStatusResponse(BaseModel):
    """调度运行状态响应"""
    isEnabled: bool = Field(..., description="是否启用")
    intervalHours: int = Field(..., description="调度间隔（小时）")
    lastRunAt: Optional[str] = Field(None, description="上次执行时间")
    lastRunStatus: Optional[str] = Field(None, description="上次执行状态")
    nextRunAt: Optional[str] = Field(None, description="下次执行时间")
    isCollecting: bool = Field(False, description="是否正在采集中")
