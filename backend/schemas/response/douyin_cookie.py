from pydantic import BaseModel, Field
from typing import Optional


class DouyinLoginStartResponse(BaseModel):
    """抖音登录启动响应"""
    sessionId: str = Field(..., description="登录会话 ID")
    qrCodeBase64: str = Field(..., description="二维码图片 Base64")
    error: Optional[str] = Field(None, description="错误信息")


class DouyinLoginStatusResponse(BaseModel):
    """抖音登录状态响应"""
    status: str = Field(..., description="登录状态: pending / success / timeout / failed / not_found")
    message: str = Field(..., description="状态描述")


class DouyinCookieStatusResponse(BaseModel):
    """抖音 Cookie 状态响应"""
    hasCookie: bool = Field(..., description="是否已有 Cookie")
    status: str = Field(..., description="Cookie 状态: active / expired / none")
    expiresAt: Optional[str] = Field(None, description="预计过期时间")
    updatedAt: Optional[str] = Field(None, description="最后更新时间")


class DouyinCookieDeleteResponse(BaseModel):
    """抖音 Cookie 删除响应"""
    success: bool = Field(..., description="是否删除成功")
    message: str = Field(..., description="操作结果")
