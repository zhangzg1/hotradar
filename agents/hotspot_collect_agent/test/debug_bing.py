"""
Bing HTML 结构分析

用于调试 Bing 搜索结果的 HTML 解析

运行方式:
    conda activate ai-hotspot-monitor
    python -m agents.hotspot_collect_agent.test.debug_bing
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from agents.hotspot_collect_agent.utils import get_random_user_agent
from agents.hotspot_collect_agent.tools import _get_bing_headers, _get_bing_cookies


async def debug_bing_html(keyword: str = "Hermes Agent"):
    """
    分析 Bing 搜索返回的 HTML 结构
    """
    print(f"\n{'='*60}")
    print(f"Bing HTML 结构分析")
    print(f"关键词: {keyword}")
    print("="*60)

    url = "https://www.bing.com/search"
    params = {"q": keyword, "count": 20}

    headers = _get_bing_headers()
    headers["Cookie"] = _get_bing_cookies()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                print(f"HTTP 状态码: {response.status}")

                if response.status != 200:
                    error_text = await response.text()
                    print(f"错误响应: {error_text[:500]}")
                    return

                html = await response.text()
                print(f"HTML 长度: {len(html)} 字符")

        # 解析 HTML
        soup = BeautifulSoup(html, "lxml")

        # 检查各种可能的结果容器
        print("\n" + "-"*40)
        print("检查 CSS 选择器匹配情况:")
        print("-"*40)

        selectors = [
            "li.b_algo",
            "#b_results .b_algo",
            ".b_algo",
            "li.b_algo h2 a",
            "#b_results > li",
            ".b_searchResult",
            "ol#b_results li",
            "div.b_title",
            "h2.b_topTitle",
            "a.b_algo",
        ]

        for selector in selectors:
            elements = soup.select(selector)
            print(f"  '{selector}': {len(elements)} 个元素")

        # 打印每个 li.b_algo 的完整内容
        print("\n" + "-"*40)
        print("li.b_algo 元素详细内容:")
        print("-"*40)

        algo_items = soup.select("li.b_algo")
        for i, item in enumerate(algo_items[:3], 1):  # 只显示前3个
            print(f"\n[元素 {i}]")
            # 打印元素的 HTML (前800字符)
            item_html = str(item)[:800]
            print(f"HTML: {item_html}")

            # 尝试提取标题
            title_elem = item.select_one("h2 a")
            if title_elem:
                print(f"标题: {title_elem.get_text(strip=True)}")
                href = title_elem.get("href", "")
                print(f"href 属性: {href}")

                # 检查是否有 data-url 或其他属性
                data_url = title_elem.get("data-url", "")
                if data_url:
                    print(f"data-url: {data_url}")

                # 检查 href 是否是 Bing 重定向链接
                if href.startswith("https://www.bing.com/ck/a?"):
                    print("⚠️  这是 Bing 重定向链接，需要解析真实 URL")

            # 尝试提取摘要
            snippet_elem = item.select_one(".b_caption p")
            if snippet_elem:
                print(f"摘要: {snippet_elem.get_text(strip=True)[:100]}")
            else:
                print("摘要: 未找到 .b_caption p")

        # 检查是否有其他结果容器
        print("\n" + "-"*40)
        print("其他可能的结果容器:")
        print("-"*40)

        other_containers = soup.select("#b_results > li:not(.b_algo)")
        for i, item in enumerate(other_containers, 1):
            item_class = item.get("class", [])
            print(f"  [{i}] class: {item_class}")
            print(f"      HTML片段: {str(item)[:200]}...")

        # 检查是否有反爬特征
        print("\n" + "-"*40)
        print("反爬检测:")
        print("-"*40)

        captcha = soup.select_one(".captcha, #captcha, .b_wlBlRaceCaptcha")
        if captcha:
            print("⚠️  发现验证码页面")
            print(f"验证码元素: {str(captcha)[:200]}")

        # 检查是否有 JavaScript 渲染的内容
        script_tags = soup.select("script")
        print(f"\nScript 标签数量: {len(script_tags)}")

        # 查找可能的 JSON 数据
        for script in script_tags[:3]:
            script_content = script.string or ""
            if "results" in script_content.lower() or "data" in script_content.lower():
                print(f"发现可能的数据脚本: {script_content[:300]}...")

        redirect = soup.select_one("meta[http-equiv='refresh']")
        if redirect:
            print(f"⚠️  发现重定向: {redirect}")

        # 打印页面标题
        title = soup.select_one("title")
        if title:
            print(f"页面标题: {title.get_text(strip=True)}")

    except Exception as e:
        print(f"❌ 错误: {e}")


if __name__ == "__main__":
    asyncio.run(debug_bing_html())