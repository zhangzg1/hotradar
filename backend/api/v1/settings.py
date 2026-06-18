"""
应用设置接口
GET /settings - 获取设置
PUT /settings - 更新设置
POST /settings/test-llm - 测试 LLM 连通性
POST /settings/test-twitter - 测试 Twitter API Key
"""
from fastapi import APIRouter, Depends

from backend.common.auth import get_current_user
from backend.schemas.request.settings import SettingsUpdateRequest, LLMTestRequest, TwitterTestRequest
from backend.schemas.response.settings import SettingsResponse, LLMTestResponse, TwitterTestResponse
from backend.services import settings_service

router = APIRouter()


@router.get(
    "",
    response_model=SettingsResponse,
    summary="获取应用设置",
    description="获取 LLM、邮箱、Twitter API 等配置",
)
async def get_settings(current_user: str = Depends(get_current_user)):
    data = await settings_service.get_settings(current_user)
    data["twitterConfigured"] = bool(data.get("twitterApiKey"))
    return SettingsResponse(**data)


@router.put(
    "",
    response_model=SettingsResponse,
    summary="更新应用设置",
    description="更新应用设置",
)
async def update_settings(request: SettingsUpdateRequest, current_user: str = Depends(get_current_user)):
    data = await settings_service.update_settings(current_user, request.model_dump(exclude_unset=True))
    return SettingsResponse(**data)


@router.post(
    "/test-llm",
    response_model=LLMTestResponse,
    summary="测试 LLM 连通性",
    description="使用提供的 Base URL、API Key 和模型名称测试 LLM 是否可正常调用",
)
async def test_llm(request: LLMTestRequest, current_user: str = Depends(get_current_user)):
    result = await settings_service.test_llm(current_user, request.baseUrl, request.apiKey, request.modelName)
    return LLMTestResponse(**result)


@router.post(
    "/test-twitter",
    response_model=TwitterTestResponse,
    summary="测试 Twitter API Key",
    description="验证 Twitter API Key 是否有效",
)
async def test_twitter(request: TwitterTestRequest, current_user: str = Depends(get_current_user)):
    result = await settings_service.test_twitter(current_user, request.apiKey)
    return TwitterTestResponse(**result)
