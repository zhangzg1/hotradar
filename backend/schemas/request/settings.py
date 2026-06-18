from pydantic import BaseModel, Field
from typing import Optional


class LLMTestRequest(BaseModel):
    """LLM 连通性测试请求"""
    baseUrl: str = Field(..., description="LLM Base URL")
    apiKey: str = Field(..., description="LLM API Key")
    modelName: str = Field(..., description="模型名称")


class TwitterTestRequest(BaseModel):
    """Twitter API 测试请求"""
    apiKey: str = Field(..., description="Twitter API Key")


class SettingsUpdateRequest(BaseModel):
    """更新设置请求"""
    llmBaseUrl: Optional[str] = Field(None, description="LLM Base URL")
    llmApiKey: Optional[str] = Field(None, description="LLM API Key (明文，后端加密存储)")
    llmModelName: Optional[str] = Field(None, description="模型名称")
    llmTested: Optional[bool] = Field(None, description="LLM 测试状态")
    notifyEmail: Optional[str] = Field(None, description="收件邮箱")
    twitterApiKey: Optional[str] = Field(None, description="Twitter API Key (明文，后端加密存储)")
    twitterTested: Optional[bool] = Field(None, description="Twitter 测试状态")
