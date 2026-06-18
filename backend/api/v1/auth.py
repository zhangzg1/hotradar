"""
认证路由
用户注册和登录
"""
from fastapi import APIRouter
from pydantic import BaseModel

from backend.services.auth_service import register_user, authenticate_user, create_access_token
from backend.common.logger import logger

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
async def register(req: RegisterRequest):
    """用户注册"""
    username = req.username.strip()
    if not username:
        return {"success": False, "message": "用户名不能为空"}

    try:
        result = await register_user(username, req.password)
        return {"success": True, "data": result}
    except ValueError as e:
        return {"success": False, "message": str(e)}


@router.post("/login")
async def login(req: LoginRequest):
    """用户登录"""
    try:
        result = await authenticate_user(req.username, req.password)
        token = create_access_token(result["userId"], result["username"])
        return {
            "success": True,
            "data": {
                "token": token,
                "username": result["username"],
                "userId": result["userId"],
            },
        }
    except ValueError as e:
        return {"success": False, "message": str(e)}
