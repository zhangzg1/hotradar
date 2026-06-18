"""错误响应体"""
from pydantic import BaseModel, Field
from typing import Optional


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="详细错误信息")