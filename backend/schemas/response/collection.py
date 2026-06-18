"""采集任务响应体"""
from pydantic import BaseModel, Field


class CollectionResponse(BaseModel):
    """采集任务响应"""
    taskId: str = Field(..., description="任务ID")
    status: str = Field("running", description="任务状态")
    message: str = Field("采集任务已启动", description="提示消息")