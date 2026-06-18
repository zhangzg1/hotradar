"""
认证服务
处理用户注册、登录、JWT 令牌管理
"""
import os
import uuid
from datetime import datetime, timedelta

from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy import select

from backend.common.mysql import AsyncSessionLocal
from backend.models.user import User
from backend.common.logger import logger

# JWT 配置
JWT_SECRET_KEY_ENV = "JWT_SECRET_KEY"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7

# 密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _get_or_create_jwt_secret() -> str:
    """从 .env 获取 JWT 密钥，不存在则自动生成并写入"""
    key = os.getenv(JWT_SECRET_KEY_ENV)
    if key:
        return key

    # 尝试手动加载 .env
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        load_dotenv(Path(__file__).parent.parent.parent / ".env")
        key = os.getenv(JWT_SECRET_KEY_ENV)
        if key:
            return key
    except ImportError:
        pass

    from cryptography.fernet import Fernet
    new_key = Fernet.generate_key().decode()
    env_path = os.path.join(os.getcwd(), ".env")

    try:
        with open(env_path, "a", encoding="utf-8") as f:
            f.write(f"\n{JWT_SECRET_KEY_ENV}={new_key}\n")
        logger.info(f"已自动生成 {JWT_SECRET_KEY_ENV} 并写入 .env")
    except Exception as e:
        logger.warning(f"无法写入 .env: {e}，使用临时密钥（重启后失效）")

    return new_key


_jwt_secret: str | None = None


def _get_jwt_secret() -> str:
    global _jwt_secret
    if _jwt_secret is None:
        _jwt_secret = _get_or_create_jwt_secret()
    return _jwt_secret


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


async def register_user(username: str, password: str) -> dict:
    """注册新用户"""
    if len(password) < 6:
        raise ValueError("密码长度至少 6 位")

    async with AsyncSessionLocal() as session:
        existing = await session.execute(
            select(User).where(User.username == username)
        )
        if existing.scalar_one_or_none():
            raise ValueError("用户名已存在")

        user = User(
            id=str(uuid.uuid4()),
            username=username,
            hashedPassword=hash_password(password),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        return {"userId": user.id, "username": user.username}


async def authenticate_user(username: str, password: str) -> dict:
    """验证用户登录"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.hashedPassword):
            raise ValueError("用户名或密码错误")

        return {"userId": user.id, "username": user.username}


def create_access_token(user_id: str, username: str) -> str:
    """创建 JWT 令牌"""
    expire = datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "name": username,
        "exp": expire,
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict | None:
    """验证 JWT 令牌"""
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
