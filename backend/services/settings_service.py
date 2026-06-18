"""
应用设置服务
管理 LLM、邮箱、Twitter API 等配置（per-user）
"""
import re
import asyncio
import uuid
from typing import Optional

from sqlalchemy import select
from langchain_openai import ChatOpenAI

from backend.common.mysql import AsyncSessionLocal
from backend.common.crypto import encrypt, decrypt
from backend.models.app_settings import AppSettings
from backend.common.logger import logger


def _normalize_base_url(url: str) -> str:
    """规范化 LLM Base URL，确保包含 /v1 路径

    用户可能只输入域名如 https://xiaoai.plus/，
    OpenAI SDK 需要完整路径如 https://xiaoai.plus/v1/
    """
    url = url.rstrip('/')
    if re.search(r'/v\d+$', url):
        return url + '/'
    return url + '/v1/'


async def _get_or_create_settings(user_id: str) -> AppSettings:
    """获取或创建设置（per-user）"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings).where(AppSettings.userId == user_id)
        )
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = AppSettings(id=str(uuid.uuid4()), userId=user_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        return settings


async def get_settings(user_id: str) -> dict:
    """获取完整设置（API Key 返回解密后的明文，前端用 password 输入框自动遮盖）"""
    settings = await _get_or_create_settings(user_id)
    return {
        "llmBaseUrl": settings.llmBaseUrl,
        "llmApiKey": decrypt(settings.llmApiKey) if settings.llmApiKey else None,
        "llmModelName": settings.llmModelName,
        "llmTested": settings.llmTested,
        "notifyEmail": settings.notifyEmail,
        "twitterApiKey": decrypt(settings.twitterApiKey) if settings.twitterApiKey else None,
        "twitterTested": settings.twitterTested,
    }


async def update_settings(user_id: str, data: dict) -> dict:
    """
    更新设置

    - API Key 传入遮盖值(如 ****FhCA)时视为未修改，不覆盖已存储的密钥
    - 切换 LLM 模型或 Base URL 时自动重置 llmTested
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings).where(AppSettings.userId == user_id)
        )
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = AppSettings(id=str(uuid.uuid4()), userId=user_id)
            session.add(settings)

        # LLM 配置
        if "llmBaseUrl" in data:
            if settings.llmBaseUrl != data["llmBaseUrl"]:
                settings.llmBaseUrl = data["llmBaseUrl"]
                settings.llmTested = False
        if "llmModelName" in data:
            if settings.llmModelName != data["llmModelName"]:
                settings.llmModelName = data["llmModelName"]
                settings.llmTested = False
        if "llmApiKey" in data:
            if data["llmApiKey"] is not None:
                settings.llmApiKey = encrypt(data["llmApiKey"])
                settings.llmTested = False
            else:
                settings.llmApiKey = None
                settings.llmTested = False
        if "llmTested" in data and data["llmTested"] is not None:
            settings.llmTested = data["llmTested"]

        # 收件邮箱
        if "notifyEmail" in data:
            settings.notifyEmail = data["notifyEmail"]

        # Twitter API Key
        if "twitterApiKey" in data:
            if data["twitterApiKey"] is not None:
                settings.twitterApiKey = encrypt(data["twitterApiKey"])
                settings.twitterTested = False
            else:
                settings.twitterApiKey = None
                settings.twitterTested = False
        if "twitterTested" in data and data["twitterTested"] is not None:
            settings.twitterTested = data["twitterTested"]

        await session.commit()
        await session.refresh(settings)

    logger.info(f"设置已更新: llm={settings.llmBaseUrl}/{settings.llmModelName}, "
                f"email={settings.notifyEmail}, twitter={'已配置' if settings.twitterApiKey else '未配置'}")

    return await get_settings(user_id)


async def test_llm(user_id: str, base_url: str, api_key: str, model_name: str) -> dict:
    """
    测试 LLM 连通性

    Returns:
        {"success": bool, "message": str}
    """
    try:
        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=_normalize_base_url(base_url),
            temperature=0,
            timeout=15,
            max_tokens=10,
        )
        response = await asyncio.wait_for(
            llm.ainvoke("你好"),
            timeout=20,
        )
        if response and hasattr(response, "content"):
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(AppSettings).where(AppSettings.userId == user_id)
                )
                settings = result.scalar_one_or_none()
                if settings:
                    settings.llmTested = True
                    await session.commit()
            return {"success": True, "message": f"连接成功，模型 {model_name} 可正常调用"}
        return {"success": False, "message": "模型返回了空响应"}

    except asyncio.TimeoutError:
        return {"success": False, "message": "连接超时，请检查 Base URL 是否正确或网络是否可达"}
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg or "authentication" in error_msg.lower():
            return {"success": False, "message": "API Key 无效或认证失败"}
        if "404" in error_msg or "not found" in error_msg.lower():
            return {"success": False, "message": "模型名称不存在或 Base URL 路径错误"}
        if "Connection" in error_msg or "connect" in error_msg.lower():
            return {"success": False, "message": "无法连接到服务器，请检查 Base URL 是否正确"}
        if "SSL" in error_msg:
            return {"success": False, "message": "SSL 证书验证失败，请检查 URL 协议"}
        return {"success": False, "message": f"连接失败: {error_msg[:200]}"}


async def test_twitter(user_id: str, api_key: str) -> dict:
    """
    测试 Twitter API Key

    Returns:
        {"success": bool, "message": str}
    """
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                "https://api.twitterapi.io/twitter/tweet/advanced_search",
                params={"query": "test", "queryType": "Latest"},
                headers={"X-API-Key": api_key},
            )
            if response.status_code == 200:
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(AppSettings).where(AppSettings.userId == user_id)
                    )
                    settings = result.scalar_one_or_none()
                    if settings:
                        settings.twitterTested = True
                        await session.commit()
                return {"success": True, "message": "Twitter API Key 验证成功"}
            elif response.status_code == 401:
                return {"success": False, "message": "API Key 无效或已过期"}
            elif response.status_code == 429:
                return {"success": False, "message": "API 调用频率超限，请稍后重试"}
            else:
                return {"success": False, "message": f"验证失败 (HTTP {response.status_code}): {response.text[:200]}"}

    except asyncio.TimeoutError:
        return {"success": False, "message": "连接超时，请检查网络是否可达"}
    except Exception as e:
        return {"success": False, "message": f"验证失败: {str(e)[:200]}"}


async def is_llm_ready(user_id: str) -> bool:
    """检查 LLM 是否已配置且测试通过"""
    settings = await _get_or_create_settings(user_id)
    return bool(settings.llmBaseUrl and settings.llmApiKey and settings.llmModelName and settings.llmTested)


async def is_email_valid(user_id: str) -> bool:
    """检查邮箱是否已配置且格式正确"""
    settings = await _get_or_create_settings(user_id)
    if not settings.notifyEmail:
        return False
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', settings.notifyEmail))


async def is_twitter_configured(user_id: str) -> bool:
    """检查 Twitter API Key 是否已配置"""
    settings = await _get_or_create_settings(user_id)
    return bool(settings.twitterApiKey)
