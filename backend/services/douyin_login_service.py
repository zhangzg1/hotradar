"""
抖音 Playwright 登录服务
管理浏览器生命周期、二维码截图、登录状态轮询、自动续期
"""
import asyncio
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.common.logger import logger

USER_DATA_DIR = Path(__file__).parent.parent.parent / "agents/hotspot_collect_agent/douyin_auth/browser_data/dy_user_data_dir"

# 全局登录会话状态
_login_sessions: dict[str, dict] = {}

# 模拟真实浏览器，避免 headless 检测
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


async def start_login(user_id: str = "1") -> dict:
    """
    启动登录流程：打开 Playwright → 打开抖音 → 提取二维码

    Returns:
        {"sessionId": str, "qrCodeBase64": str}
    """
    session_id = f"douyin_login_{user_id}_{id(asyncio.get_event_loop())}"

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"sessionId": "", "qrCodeBase64": "", "error": "Playwright 未安装，请运行: pip install playwright && playwright install chromium"}

    try:
        pw = await async_playwright().start()

        user_data_path = Path(USER_DATA_DIR)
        user_data_path.mkdir(parents=True, exist_ok=True)

        browser_context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(user_data_path),
            headless=True,
            viewport={"width": 1280, "height": 800},
            user_agent=_USER_AGENT,
            accept_downloads=True,
        )

        page = await browser_context.new_page()
        await page.goto("https://www.douyin.com", wait_until="domcontentloaded", timeout=30000)

        # 等待页面渲染完成
        await asyncio.sleep(3)

        # 检查浏览器是否已有登录态（持久化浏览器数据中的旧会话）
        already_logged_in, local_storage = await _check_browser_login(page, browser_context)

        if already_logged_in:
            # 已有登录态，直接提取 Cookie 保存，不需要扫码
            logger.info("检测到浏览器已有登录态，直接提取 Cookie")
            auto_result = await _auto_login_save(
                browser_context, pw, local_storage, user_id
            )
            return auto_result

        # 无登录态，走正常二维码流程
        qr_base64 = await _extract_qr_code(page)

        if not qr_base64:
            logger.warning("未能提取到二维码图片")

        # 保存会话状态
        _login_sessions[session_id] = {
            "user_id": user_id,
            "playwright": pw,
            "browser_context": browser_context,
            "page": page,
            "status": "pending",
            "started_at": datetime.now(),
        }

        # 启动后台轮询任务
        asyncio.create_task(_poll_login_status(session_id))

        logger.info(f"抖音登录流程已启动 (session={session_id}, qr_size={len(qr_base64)})")
        return {"sessionId": session_id, "qrCodeBase64": qr_base64}

    except Exception as e:
        logger.error(f"启动登录流程失败: {e}")
        # 清理可能残留的资源
        if session_id in _login_sessions:
            await _cleanup_session(session_id)
        return {"sessionId": "", "qrCodeBase64": "", "error": f"启动失败: {str(e)[:200]}"}


async def _check_browser_login(page, browser_context) -> tuple[bool, dict]:
    """检查浏览器持久化数据中是否已有有效登录态"""
    local_storage = {}
    try:
        local_storage = await page.evaluate("() => window.localStorage")
        if local_storage.get("HasUserLogin") == "1":
            return True, local_storage
    except Exception:
        pass

    try:
        cookies = await browser_context.cookies()
        for cookie in cookies:
            if cookie.get("name") == "LOGIN_STATUS" and cookie.get("value") == "1":
                return True, local_storage
    except Exception:
        pass

    return False, local_storage


async def _auto_login_save(browser_context, pw, local_storage, user_id) -> dict:
    """已有登录态时直接提取 Cookie 保存并清理浏览器"""
    try:
        cookies = await browser_context.cookies(
            urls=["https://douyin.com", "https://www.douyin.com"]
        )
        cookie_list = [
            {
                "name": c["name"],
                "value": c["value"],
                "domain": c.get("domain", ""),
                "path": c.get("path", "/"),
            }
            for c in cookies
        ]
        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookie_list)
        ms_token = local_storage.get("xmst", "")

        from backend.services.douyin_cookie_service import save_cookie
        await save_cookie(cookie_str, user_id, ms_token)

        logger.info(f"自动登录成功，Cookie 已保存 (user={user_id})")

        from backend.common.websocket import manager
        await manager.broadcast({
            "type": "douyin_cookie_updated",
            "status": "active",
            "message": "抖音登录成功，Cookie 已保存",
        })

        await browser_context.close()
        await pw.stop()

        return {"sessionId": "", "qrCodeBase64": "", "autoLogin": True}

    except Exception as e:
        logger.error(f"自动登录保存 Cookie 失败: {e}")
        try:
            await browser_context.close()
        except Exception:
            pass
        try:
            await pw.stop()
        except Exception:
            pass
        return {"sessionId": "", "qrCodeBase64": "", "error": f"自动登录失败: {str(e)[:200]}"}


async def _extract_qr_code(page) -> str:
    """
    从抖音登录页面提取二维码
    使用多策略：JS DOM 提取 > 元素截图 > 全页截图
    """
    # ---------- 策略 1: 用 JS 直接从 DOM 中查找二维码图片 ----------
    try:
        qr_data = await page.evaluate("""() => {
            // 查找 img 标签中的 base64 图片（二维码通常是 data:image/png;base64,...）
            const imgs = [...document.querySelectorAll('img')];
            for (const img of imgs) {
                if (img.src && img.src.startsWith('data:image') && img.src.length > 1000) {
                    const rect = img.getBoundingClientRect();
                    if (rect.width > 80 && rect.height > 80) {
                        return { type: 'img', src: img.src, w: rect.width, h: rect.height };
                    }
                }
            }
            // 查找 canvas（有些页面用 canvas 渲染二维码）
            const canvases = [...document.querySelectorAll('canvas')];
            for (const c of canvases) {
                if (c.width > 80 && c.height > 80) {
                    return { type: 'canvas', dataUrl: c.toDataURL('image/png'), w: c.width, h: c.height };
                }
            }
            // 查找带 background-image 的二维码容器
            const divs = [...document.querySelectorAll('div')];
            for (const div of divs) {
                const bg = getComputedStyle(div).backgroundImage;
                if (bg && bg.includes('data:image') && bg.length > 1000) {
                    const rect = div.getBoundingClientRect();
                    if (rect.width > 80 && rect.height > 80) {
                        return { type: 'bg', src: bg, w: rect.width, h: rect.height };
                    }
                }
            }
            return null;
        }""")

        if qr_data:
            src = ""
            if qr_data["type"] in ("img", "bg"):
                raw = qr_data["src"]
                # backgroundImage 格式: url("data:image/png;base64,...")
                if qr_data["type"] == "bg":
                    start = raw.find("data:image")
                    if start >= 0:
                        end = raw.find(")", start)
                        raw = raw[start:end] if end >= 0 else raw[start:]
                src = raw
            elif qr_data["type"] == "canvas":
                src = qr_data["dataUrl"]

            if src and "," in src:
                b64 = src.split(",", 1)[1]
                if len(b64) > 500:
                    logger.info(f"JS DOM 提取二维码成功 (type={qr_data['type']}, size={len(b64)})")
                    return b64
    except Exception as e:
        logger.debug(f"JS DOM 提取失败: {e}")

    # ---------- 策略 2: 通过 CSS 选择器定位二维码元素并截图 ----------
    qr_selectors = [
        "div[data-e2e='login-qrcode']",
        "div[data-e2e='login-qrcode'] img",
        "div[data-e2e='login-qrcode'] canvas",
        "div[data-e2e='login-panel']",
        ".qrcode-img",
        ".qrcode-img img",
        "[class*='qrcode']",
        "[class*='qr-code']",
        "[class*='login-qr']",
    ]

    for selector in qr_selectors:
        try:
            el = await page.query_selector(selector)
            if not el:
                continue

            # 如果是 img，先尝试获取 src
            tag = await el.evaluate("el => el.tagName")
            if tag == "IMG":
                src = await el.get_attribute("src")
                if src and src.startswith("data:image") and "," in src:
                    b64 = src.split(",", 1)[1]
                    if len(b64) > 500:
                        logger.info(f"通过 {selector} img src 提取成功")
                        return b64
            elif tag == "CANVAS":
                data_url = await el.evaluate("el => el.toDataURL('image/png')")
                if data_url and "," in data_url:
                    b64 = data_url.split(",", 1)[1]
                    if len(b64) > 500:
                        logger.info(f"通过 {selector} canvas 提取成功")
                        return b64

            # 截图该元素
            box = await el.bounding_box()
            if box and box["width"] > 50 and box["height"] > 50:
                screenshot = await el.screenshot(type="png")
                b64 = base64.b64encode(screenshot).decode("utf-8")
                if len(b64) > 2000:
                    logger.info(f"通过 {selector} 元素截图成功 (size={len(b64)})")
                    return b64
        except Exception as e:
            logger.debug(f"选择器 {selector} 失败: {e}")

    # ---------- 策略 3: 全页面截图（最后手段）----------
    try:
        screenshot = await page.screenshot(type="png", full_page=False)
        b64 = base64.b64encode(screenshot).decode("utf-8")
        logger.warning(f"只能使用全页面截图，二维码可能不清晰 (size={len(b64)})")
        return b64
    except Exception as e:
        logger.error(f"全页面截图失败: {e}")
        return ""


async def _poll_login_status(session_id: str):
    """后台轮询登录状态"""
    session = _login_sessions.get(session_id)
    if not session:
        return

    page = session["page"]
    browser_context = session["browser_context"]
    max_wait = 180  # 3 分钟超时

    for i in range(max_wait):
        if session["status"] != "pending":
            break

        await asyncio.sleep(1)

        # 检查 localStorage
        try:
            local_storage = await page.evaluate("() => window.localStorage")
            if local_storage.get("HasUserLogin") == "1":
                session["status"] = "success"
                await _on_login_success(session_id, local_storage)
                return
        except Exception:
            pass

        # 检查 Cookie
        try:
            cookies = await browser_context.cookies()
            for cookie in cookies:
                if cookie.get("name") == "LOGIN_STATUS" and cookie.get("value") == "1":
                    session["status"] = "success"
                    try:
                        local_storage = await page.evaluate("() => window.localStorage")
                    except Exception:
                        local_storage = {}
                    await _on_login_success(session_id, local_storage)
                    return
        except Exception:
            pass

    # 超时
    if session["status"] == "pending":
        session["status"] = "timeout"
        await _cleanup_session(session_id)
        logger.warning(f"抖音登录超时 (session={session_id})")


async def _on_login_success(session_id: str, local_storage: dict):
    """登录成功后提取 Cookie 并保存到数据库"""
    session = _login_sessions.get(session_id)
    if not session:
        return

    browser_context = session["browser_context"]
    user_id = session["user_id"]

    try:
        # 提取 Cookie
        cookies = await browser_context.cookies(urls=["https://douyin.com", "https://www.douyin.com"])
        cookie_list = []
        for cookie in cookies:
            cookie_list.append({
                "name": cookie["name"],
                "value": cookie["value"],
                "domain": cookie.get("domain", ""),
                "path": cookie.get("path", "/"),
            })

        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookie_list])
        ms_token = local_storage.get("xmst", "")

        # 保存到数据库
        from backend.services.douyin_cookie_service import save_cookie
        await save_cookie(cookie_str, user_id, ms_token)

        logger.info(f"抖音登录成功，Cookie 已保存 (user={user_id})")

        # 通知前端
        from backend.common.websocket import manager
        await manager.broadcast({
            "type": "douyin_cookie_updated",
            "status": "active",
            "message": "抖音登录成功，Cookie 已保存",
        })

    except Exception as e:
        logger.error(f"保存抖音 Cookie 失败: {e}")
        session["status"] = "failed"
    finally:
        await _cleanup_session(session_id)


async def _cleanup_session(session_id: str):
    """清理浏览器资源"""
    session = _login_sessions.pop(session_id, None)
    if not session:
        return

    try:
        await session["browser_context"].close()
    except Exception:
        pass

    try:
        await session["playwright"].stop()
    except Exception:
        pass


async def get_login_status(session_id: str) -> dict:
    """查询登录状态"""
    session = _login_sessions.get(session_id)
    if not session:
        return {"status": "not_found", "message": "登录会话不存在或已过期"}

    status = session["status"]
    message_map = {
        "pending": "等待扫码登录",
        "success": "登录成功，Cookie 已保存",
        "timeout": "登录超时，请重新尝试",
        "failed": "登录失败",
    }

    return {
        "status": status,
        "message": message_map.get(status, status),
    }


async def renew_cookie_via_browser(user_id: str = "1") -> dict:
    """
    使用持久化浏览器上下文尝试自动续期 Cookie

    如果浏览器 Session 未完全过期，重新访问抖音可以刷新 Cookie
    Returns:
        {"success": bool, "message": str}
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"success": False, "message": "Playwright 未安装"}

    try:
        pw = await async_playwright().start()
        user_data_path = Path(USER_DATA_DIR)
        if not user_data_path.exists():
            await pw.stop()
            return {"success": False, "message": "无持久化浏览器数据，无法续期"}

        browser_context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(user_data_path),
            headless=True,
            viewport={"width": 1280, "height": 800},
            user_agent=_USER_AGENT,
        )

        page = await browser_context.new_page()
        await page.goto("https://www.douyin.com", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # 检查是否仍然登录
        local_storage = {}
        logged_in = False
        try:
            local_storage = await page.evaluate("() => window.localStorage")
            if local_storage.get("HasUserLogin") == "1":
                logged_in = True
        except Exception:
            pass

        # 也检查 Cookie
        if not logged_in:
            try:
                cookies = await browser_context.cookies()
                for cookie in cookies:
                    if cookie.get("name") == "LOGIN_STATUS" and cookie.get("value") == "1":
                        logged_in = True
                        break
            except Exception:
                pass

        if logged_in:
            # 重新提取 Cookie 并保存
            cookies = await browser_context.cookies(urls=["https://douyin.com", "https://www.douyin.com"])
            cookie_list = [{"name": c["name"], "value": c["value"], "domain": c.get("domain", ""), "path": c.get("path", "/")} for c in cookies]
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookie_list])
            ms_token = local_storage.get("xmst", "")

            from backend.services.douyin_cookie_service import save_cookie
            await save_cookie(cookie_str, user_id, ms_token)

            await browser_context.close()
            await pw.stop()
            return {"success": True, "message": "Cookie 自动续期成功"}

        await browser_context.close()
        await pw.stop()
        return {"success": False, "message": "浏览器 Session 已过期，需要重新扫码登录"}

    except Exception as e:
        logger.error(f"Cookie 自动续期异常: {e}")
        return {"success": False, "message": f"续期异常: {str(e)[:200]}"}
