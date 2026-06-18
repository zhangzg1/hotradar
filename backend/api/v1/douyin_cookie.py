"""
抖音 Cookie 管理接口
POST /douyin-cookie/login/start   - 启动登录流程
GET  /douyin-cookie/login/status   - 查询登录状态
GET  /douyin-cookie/status         - 查询 Cookie 状态
DELETE /douyin-cookie              - 删除 Cookie（退出登录）
"""
from fastapi import APIRouter, Depends

from backend.common.auth import get_current_user
from backend.schemas.response.douyin_cookie import (
    DouyinLoginStartResponse,
    DouyinLoginStatusResponse,
    DouyinCookieStatusResponse,
    DouyinCookieDeleteResponse,
)
from backend.services import douyin_login_service, douyin_cookie_service

router = APIRouter()


@router.post(
    "/login/start",
    response_model=DouyinLoginStartResponse,
    summary="启动抖音登录",
    description="启动 Playwright 浏览器，获取抖音登录二维码",
)
async def start_douyin_login(current_user: str = Depends(get_current_user)):
    result = await douyin_login_service.start_login(current_user)
    return DouyinLoginStartResponse(**result)


@router.get(
    "/login/status",
    response_model=DouyinLoginStatusResponse,
    summary="查询抖音登录状态",
    description="轮询登录状态，检查用户是否已扫码完成登录",
)
async def get_douyin_login_status(sessionId: str, current_user: str = Depends(get_current_user)):
    result = await douyin_login_service.get_login_status(sessionId)
    return DouyinLoginStatusResponse(**result)


@router.get(
    "/status",
    response_model=DouyinCookieStatusResponse,
    summary="查询抖音 Cookie 状态",
    description="获取当前 Cookie 是否存在、是否有效、过期时间等信息",
)
async def get_douyin_cookie_status(current_user: str = Depends(get_current_user)):
    data = await douyin_cookie_service.get_cookie_status(current_user)
    return DouyinCookieStatusResponse(**data)


@router.delete(
    "",
    response_model=DouyinCookieDeleteResponse,
    summary="删除抖音 Cookie",
    description="删除已保存的 Cookie，相当于退出抖音登录",
)
async def delete_douyin_cookie(current_user: str = Depends(get_current_user)):
    success = await douyin_cookie_service.delete_cookie(current_user)
    return DouyinCookieDeleteResponse(
        success=success,
        message="Cookie 已删除" if success else "无 Cookie 可删除",
    )
