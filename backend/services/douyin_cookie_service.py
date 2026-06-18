"""
抖音 Cookie 管理服务
管理 Cookie 的加密存储、读取、有效性检测、自动续期
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select

from backend.common.mysql import AsyncSessionLocal
from backend.common.crypto import encrypt, decrypt
from backend.models.douyin_cookie import DouyinCookie
from backend.common.logger import logger


async def _get_or_create_cookie(user_id: str) -> DouyinCookie:
    """获取或创建 Cookie 记录（单行/每用户）"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DouyinCookie).where(DouyinCookie.userId == user_id)
        )
        cookie = result.scalar_one_or_none()
        if cookie is None:
            cookie = DouyinCookie(id=str(uuid.uuid4()), userId=user_id)
            session.add(cookie)
            await session.commit()
            await session.refresh(cookie)
        return cookie


async def get_cookie_status(user_id: str) -> dict:
    """获取 Cookie 状态（不含解密内容，供 API 使用）"""
    cookie = await _get_or_create_cookie(user_id)
    has_cookie = bool(cookie.cookieString)

    # 验证加密数据能否解密，解密失败则视为无效
    if has_cookie:
        cookie_str = decrypt(cookie.cookieString)
        if not cookie_str:
            logger.warning(f"抖音 Cookie 解密失败，标记为无效 (user={user_id})")
            await _clear_corrupted_cookie(user_id)
            has_cookie = False

    return {
        "hasCookie": has_cookie,
        "status": cookie.status if has_cookie else "none",
        "expiresAt": cookie.expiresAt.isoformat() if has_cookie and cookie.expiresAt else None,
        "updatedAt": cookie.updatedAt.isoformat() if cookie.updatedAt else None,
    }


async def get_decrypted_cookie(user_id: str) -> tuple[str, str]:
    """
    获取解密后的 Cookie 和 msToken（供抓取 Agent 使用）

    Returns:
        (cookie_string, ms_token) 元组，无 Cookie 时返回 ("", "")
    """
    cookie = await _get_or_create_cookie(user_id)
    if not cookie.cookieString:
        return "", ""
    cookie_str = decrypt(cookie.cookieString)
    ms_token = decrypt(cookie.msToken) if cookie.msToken else ""
    return cookie_str, ms_token


async def is_douyin_cookie_active(user_id: str) -> bool:
    """检查是否有有效的抖音 Cookie（能解密且未过期）"""
    cookie = await _get_or_create_cookie(user_id)
    if not cookie.cookieString or cookie.status != "active":
        return False
    # 验证解密
    cookie_str = decrypt(cookie.cookieString)
    if not cookie_str:
        logger.warning(f"抖音 Cookie 解密失败 (user={user_id})")
        await _clear_corrupted_cookie(user_id)
        return False
    return True


async def _clear_corrupted_cookie(user_id: str):
    """清除无法解密的损坏 Cookie"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DouyinCookie).where(DouyinCookie.userId == user_id)
        )
        cookie = result.scalar_one_or_none()
        if cookie and cookie.cookieString:
            cookie.cookieString = None
            cookie.msToken = None
            cookie.status = "none"
            cookie.expiresAt = None
            cookie.updatedAt = datetime.now()
            await session.commit()
            logger.info(f"已清除损坏的抖音 Cookie (user={user_id})")


async def save_cookie(
    cookie_string: str,
    user_id: str,
    ms_token: str = "",
    expires_days: int = 14,
) -> dict:
    """加密存储 Cookie"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DouyinCookie).where(DouyinCookie.userId == user_id)
        )
        cookie = result.scalar_one_or_none()
        if cookie is None:
            cookie = DouyinCookie(id=str(uuid.uuid4()), userId=user_id)
            session.add(cookie)

        cookie.cookieString = encrypt(cookie_string)
        cookie.msToken = encrypt(ms_token) if ms_token else None
        cookie.status = "active"
        cookie.expiresAt = datetime.now() + timedelta(days=expires_days)
        cookie.updatedAt = datetime.now()

        await session.commit()
        await session.refresh(cookie)

    logger.info(f"抖音 Cookie 已保存 (user={user_id})")
    return await get_cookie_status(user_id)


async def delete_cookie(user_id: str) -> bool:
    """删除 Cookie（退出登录）"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DouyinCookie).where(DouyinCookie.userId == user_id)
        )
        cookie = result.scalar_one_or_none()
        if cookie and cookie.cookieString:
            cookie.cookieString = None
            cookie.msToken = None
            cookie.status = "none"
            cookie.expiresAt = None
            cookie.updatedAt = datetime.now()
            await session.commit()
            logger.info(f"抖音 Cookie 已删除 (user={user_id})")
            return True
    return False


async def check_cookie_validity(user_id: str) -> dict:
    """
    检测 Cookie 是否仍然有效

    通过发一次轻量请求判断 Cookie 是否过期
    Returns:
        {"valid": bool, "message": str}
    """
    cookie_str, ms_token = await get_decrypted_cookie(user_id)
    if not cookie_str:
        return {"valid": False, "message": "未配置 Cookie"}

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Cookie": cookie_str,
                "Referer": "https://www.douyin.com/",
            }
            resp = await client.get(
                "https://www.douyin.com/aweme/v1/web/general/search/single/",
                params={"keyword": "test", "count": "1", "offset": "0"},
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                # 检查是否返回 verify_check（说明 Cookie 过期）
                if isinstance(data, dict):
                    search_nil = data.get("data", {}).get("search_nil_info", "")
                    if "verify_check" in str(search_nil):
                        await _mark_expired(user_id)
                        return {"valid": False, "message": "Cookie 已过期，需要重新登录"}
                return {"valid": True, "message": "Cookie 有效"}
            elif resp.status_code == 403:
                await _mark_expired(user_id)
                return {"valid": False, "message": "Cookie 已失效（403）"}
            else:
                return {"valid": True, "message": f"Cookie 状态未知 (HTTP {resp.status_code})"}
    except Exception as e:
        logger.warning(f"抖音 Cookie 有效性检测异常: {e}")
        return {"valid": True, "message": f"检测异常，假定有效: {str(e)[:100]}"}


async def _mark_expired(user_id: str):
    """标记 Cookie 为过期状态"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DouyinCookie).where(DouyinCookie.userId == user_id)
        )
        cookie = result.scalar_one_or_none()
        if cookie:
            cookie.status = "expired"
            cookie.updatedAt = datetime.now()
            await session.commit()
    logger.info(f"抖音 Cookie 已标记过期 (user={user_id})")


async def try_auto_renew(user_id: str) -> dict:
    """
    尝试自动续期 Cookie

    使用持久化浏览器上下文重新访问抖音，如果 Session 未过期则可续期
    Returns:
        {"success": bool, "message": str}
    """
    cookie = await _get_or_create_cookie(user_id)
    if not cookie.cookieString:
        return {"success": False, "message": "无 Cookie，无法续期"}

    try:
        from backend.services.douyin_login_service import renew_cookie_via_browser
        result = await renew_cookie_via_browser(user_id)
        if result["success"]:
            logger.info("抖音 Cookie 自动续期成功")
        else:
            await _mark_expired(user_id)
            logger.warning(f"抖音 Cookie 自动续期失败: {result['message']}")
        return result
    except Exception as e:
        logger.error(f"抖音 Cookie 自动续期异常: {e}")
        await _mark_expired(user_id)
        return {"success": False, "message": f"续期异常: {str(e)[:100]}"}
