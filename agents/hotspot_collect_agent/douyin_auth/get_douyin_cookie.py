# -*- coding: utf-8 -*-
"""
抖音 Cookie 获取脚本

运行此脚本会打开浏览器，你需要扫码登录抖音账号。
登录成功后，cookie 会保存到 douyin_cookie.json 文件，供热点采集系统使用。

使用方法:
    cd agents/hotspot_collect_agent/douyin_auth
    python get_douyin_cookie.py

注意:
    - Cookie 过期后需要重新执行此脚本
    - 新的 cookie 会覆盖旧的 cookie 文件
"""

import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright


# Cookie文件路径（保存在当前目录）
COOKIE_FILE = Path(__file__).parent / "douyin_cookie.json"
# 浏览器用户数据目录（保存在当前目录）
USER_DATA_DIR = Path(__file__).parent / "browser_data/dy_user_data_dir"


async def get_cookie():
    """
    获取抖音登录 cookie
    打开浏览器，等待用户扫码登录，然后保存 cookie
    """
    print("=" * 50)
    print("抖音 Cookie 获取脚本")
    print("=" * 50)
    print("\n即将打开浏览器，请在浏览器中扫码登录抖音账号...")
    print("登录成功后，程序会自动保存 cookie 并关闭浏览器\n")

    async with async_playwright() as playwright:
        # 使用持久化上下文保存登录状态
        user_data_path = Path(USER_DATA_DIR)
        user_data_path.mkdir(parents=True, exist_ok=True)

        browser_context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_path),
            headless=False,  # 显示浏览器，用户需要扫码
            viewport={"width": 1920, "height": 1080},
            accept_downloads=True,
        )

        page = await browser_context.new_page()

        # 访问抖音首页
        print("正在打开抖音首页...")
        await page.goto("https://www.douyin.com")

        # 等待用户登录
        print("\n请在浏览器中扫码登录...")
        print("登录成功后，页面会显示登录状态变化")
        print("程序会自动检测登录状态，请稍候...\n")

        # 检测登录状态
        max_wait_time = 120  # 最大等待时间 120秒
        logged_in = False
        local_storage = {}

        for i in range(max_wait_time):
            await asyncio.sleep(1)

            # 检查 localStorage 中的登录标志和 xmst
            try:
                local_storage = await page.evaluate("() => window.localStorage")
                if local_storage.get("HasUserLogin") == "1":
                    logged_in = True
                    print(f"\n✓ 检测到登录成功！等待 {i+1} 秒")
                    break
            except Exception:
                pass

            # 也检查 cookie
            cookies = await browser_context.cookies()
            for cookie in cookies:
                if cookie.get("name") == "LOGIN_STATUS" and cookie.get("value") == "1":
                    logged_in = True
                    print(f"\n✓ 检测到登录成功！等待 {i+1} 秒")
                    break

            if logged_in:
                break

            # 每10秒提醒一次
            if (i + 1) % 10 == 0:
                print(f"等待登录... 已等待 {i+1} 秒")

        if not logged_in:
            print("\n⚠ 未检测到登录状态，但你仍可以手动确认")
            print("如果你已经登录，请按 Enter 键继续保存 cookie...")
            # 在非交互模式下，我们假设用户已经登录
            # 再次尝试获取 localStorage
            try:
                local_storage = await page.evaluate("() => window.localStorage")
            except Exception:
                local_storage = {}

        # 获取所有 cookie
        cookies = await browser_context.cookies(urls=["https://douyin.com", "https://www.douyin.com"])

        # 转换为简洁格式
        cookie_dict = {}
        cookie_list = []
        for cookie in cookies:
            cookie_dict[cookie["name"]] = cookie["value"]
            cookie_list.append({
                "name": cookie["name"],
                "value": cookie["value"],
                "domain": cookie.get("domain", ""),
                "path": cookie.get("path", "/"),
            })

        # 生成 cookie 字符串
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookie_list])

        # 获取 msToken (xmst) 从 localStorage
        ms_token = local_storage.get("xmst", "")

        # 保存到文件
        result = {
            "cookie_string": cookie_str,
            "cookie_dict": cookie_dict,
            "cookie_list": cookie_list,
            "ms_token": ms_token,  # 添加 msToken
            "local_storage": dict(local_storage),  # 保存完整的 localStorage
        }

        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n✓ Cookie 已保存到 {COOKIE_FILE}")
        print(f"  - cookie_string: 用于 HTTP 请求")
        print(f"  - cookie_dict: 用于程序读取")
        print(f"  - cookie_list: 详细 cookie 信息")

        # 关闭浏览器
        await browser_context.close()

        print("\n浏览器已关闭")
        print("=" * 50)
        print("Cookie 已保存，热点采集系统现在可以使用抖音数据源了")
        print("=" * 50)


async def check_login_status():
    """
    检查已保存的登录状态是否有效
    """
    user_data_path = Path(USER_DATA_DIR)
    if not user_data_path.exists():
        print("未找到保存的登录状态")
        return False

    print("检查已保存的登录状态...")

    async with async_playwright() as playwright:
        browser_context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_path),
            headless=True,  # 无头模式检查
            viewport={"width": 1920, "height": 1080},
        )

        page = await browser_context.new_page()
        await page.goto("https://www.douyin.com")

        # 检查登录状态
        local_storage = await page.evaluate("() => window.localStorage")
        logged_in = local_storage.get("HasUserLogin") == "1"

        await browser_context.close()

        if logged_in:
            print("✓ 登录状态有效")
            return True
        else:
            print("⚠ 登录状态已过期，需要重新登录")
            return False


async def main():
    """主函数"""
    # 先检查是否已有有效的登录状态
    if await check_login_status():
        print("\n你已经保存了有效的登录状态")
        print("是否要重新获取 cookie？")
        print("直接运行此脚本可以更新 cookie")

    # 获取 cookie
    await get_cookie()


if __name__ == "__main__":
    asyncio.run(main())