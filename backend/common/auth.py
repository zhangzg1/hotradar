"""
认证依赖
用于 FastAPI 路由的用户认证
"""
from fastapi import Depends, HTTPException, Header

from backend.services.auth_service import verify_token


async def get_current_user(authorization: str = Header(None)) -> str:
    """
    从 Authorization 头提取并验证 JWT，返回 user_id
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")

    token = authorization[7:]
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    return payload["sub"]
