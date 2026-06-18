from pydantic import BaseModel, Field
from typing import Optional


class SettingsResponse(BaseModel):
    """设置响应"""
    llmBaseUrl: Optional[str] = Field(None, description="LLM Base URL")
    llmApiKey: Optional[str] = Field(None, description="LLM API Key")
    llmModelName: Optional[str] = Field(None, description="模型名称")
    llmTested: bool = Field(False, description="LLM 是否测试通过")
    notifyEmail: Optional[str] = Field(None, description="收件邮箱")
    twitterApiKey: Optional[str] = Field(None, description="Twitter API Key")
    twitterTested: bool = Field(False, description="Twitter API 是否测试通过")
    twitterConfigured: bool = Field(False, description="Twitter API Key 是否已配置")


class LLMTestResponse(BaseModel):
    """LLM 测试结果"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="结果消息")


class TwitterTestResponse(BaseModel):
    """Twitter API 测试结果"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="结果消息")
