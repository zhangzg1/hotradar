#!/usr/bin/env python3
"""
HotRadar - 邮件推送脚本

通过 Cloudflare Workers + Resend API 将热点分析结果发送到用户邮箱。
SMTP 凭证存储在 Workers 密钥中，代码内不包含任何敏感信息。

用法:
    python hotradar_email.py <email_config.json>

配置文件格式:
{
    "toEmail": "recipient@example.com",
    "keyword": "codex, openclaw",
    "hotspots": [
        {
            "title": "...",
            "url": "...",
            "source": "...",
            "keyword": "此热点所属的关键词",
            "relevance": 85,
            "importance": "high",
            "summary": "..."
        }
    ]
}
"""
import asyncio
import json
import sys
import logging

import aiohttp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("hotradar-email")

# Workers API 配置（公开信息，不含任何密码）
WORKERS_URL = "https://hotradar-email.vercel.app/api/send"
WORKERS_TOKEN = "hr_email_2026"

IMPORTANCE_EMOJI = {"urgent": "🚨", "high": "🔥", "medium": "⚡", "low": "📌"}
SOURCE_NAMES = {
    "twitter": "Twitter", "youtube": "YouTube", "bilibili": "Bilibili",
    "douyin": "抖音", "bing": "Bing", "sogou": "搜狗",
}


def _build_email_html(config: dict) -> str:
    hotspots = config.get("hotspots", [])
    keyword_str = config.get("keyword", "")
    keywords = [k.strip() for k in keyword_str.split(",") if k.strip()]

    # 按关键词分组
    grouped: dict[str, list] = {}
    for h in hotspots:
        kw = h.get("keyword", "未知关键词")
        if kw not in grouped:
            grouped[kw] = []
        grouped[kw].append(h)

    # 每个关键词组内按重要性排序（urgent > high > medium > low）
    importance_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    for kw in grouped:
        grouped[kw].sort(key=lambda x: (importance_order.get(x.get("importance", "low"), 3), -(x.get("relevance", 0))))

    total_count = len(hotspots)
    keyword_count = len(grouped)

    # 时间范围
    from datetime import datetime, timedelta
    time_range_end = datetime.now()
    time_range_start = time_range_end - timedelta(hours=168)
    time_start_str = time_range_start.strftime("%Y-%m-%d %H:%M")
    time_end_str = time_range_end.strftime("%Y-%m-%d %H:%M")

    # 统计摘要
    summary_parts = [f'共 <strong>{total_count}</strong> 条重要热点']
    if keyword_count > 1:
        summary_parts.append(f'涉及 <strong>{keyword_count}</strong> 个关键词')
    summary_text = ' | '.join(summary_parts)

    # 关键词分组 HTML
    keyword_sections_html = ""
    for kw in keywords:
        items = grouped.get(kw, [])
        if not items:
            continue

        section_items = ""
        for h in items:
            importance = h.get("importance", "low")
            emoji = IMPORTANCE_EMOJI.get(importance, "📌")
            title = h.get("title", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if len(title) > 80:
                title = title[:80] + "..."
            source_name = SOURCE_NAMES.get(h.get("source", ""), h.get("source", ""))
            summary = h.get("summary", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if len(summary) > 200:
                summary = summary[:200] + "..."
            url = h.get("url", "#")

            badge_class = f"badge-{importance}"
            importance_label = importance.upper()

            section_items += f'''
            <div class="hotspot-item">
                <div class="hotspot-title">{emoji} <span class="badge {badge_class}">{importance_label}</span> {title}</div>
                <div class="hotspot-meta">来源：{source_name}</div>
                {f'<p>{summary}</p>' if summary else ''}
                <a class="link" href="{url}">查看原文 →</a>
            </div>'''

        keyword_sections_html += f'''
        <div class="keyword-section">
            <div class="keyword-title">🔍 关键词：{kw}</div>
            <p>该关键词下 {len(items)} 条热点</p>
            {section_items}
        </div>'''

    html = f'''
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }}
.container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
.header {{ border-bottom: 2px solid #eee; padding-bottom: 20px; }}
.header h1 {{ color: #333; margin: 0; }}
.summary {{ background: #f9f9f9; padding: 15px; border-radius: 4px; margin: 20px 0; }}
.keyword-section {{ margin: 20px 0; padding: 15px; border-left: 4px solid #007bff; }}
.keyword-title {{ font-weight: bold; color: #007bff; margin-bottom: 10px; }}
.hotspot-item {{ padding: 10px 0; border-bottom: 1px solid #eee; }}
.hotspot-title {{ font-weight: bold; color: #333; }}
.hotspot-meta {{ color: #666; font-size: 12px; }}
.badge {{ padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
.badge-urgent {{ background: #dc3545; color: white; }}
.badge-high {{ background: #fd7e14; color: white; }}
.badge-medium {{ background: #ffc107; color: #333; }}
.badge-low {{ background: #28a745; color: white; }}
.link {{ color: #007bff; text-decoration: none; }}
.footer {{ margin-top: 20px; padding-top: 20px; border-top: 2px solid #eee; color: #666; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>📊 AI热点监控 - 您有 {total_count} 条重要热点待查看</h1>
    </div>
    <div class="summary">
        <p>{summary_text}</p>
        <p>时间范围：{time_start_str} ~ {time_end_str}</p>
    </div>
    {keyword_sections_html}
    <div class="footer">
        <p>Powered by HotRadar - AI 热点监控与采集工具</p>
    </div>
</div>
</body>
</html>'''
    return html


async def send_email(config: dict) -> bool:
    to_email = config.get("toEmail", "")
    if not to_email:
        logger.error("No recipient email provided")
        return False

    keyword = config.get("keyword", "")
    hotspots = config.get("hotspots", [])
    subject = f"【AI热点监控】您有 {len(hotspots)} 条重要热点待查看 - {keyword}"
    html_content = _build_email_html(config)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                WORKERS_URL,
                json={
                    "toEmail": to_email,
                    "subject": subject,
                    "html": html_content,
                },
                headers={
                    "Authorization": f"Bearer {WORKERS_TOKEN}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Email sent to {to_email}, id={data.get('id')}")
                    return True
                else:
                    err = await resp.text()
                    logger.error(f"Email send failed (HTTP {resp.status}): {err}")
                    return False
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


async def main(config_path: str):
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    success = await send_email(config)
    if success:
        print("✅ Email sent successfully!")
    else:
        print("❌ Email send failed!")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <email_config.json>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
