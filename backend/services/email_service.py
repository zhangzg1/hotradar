"""
邮件服务模块
SMTP 配置、邮件模板渲染和发送逻辑
"""
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from dotenv import load_dotenv

from backend.models import Hotspot, Keyword
from backend.common.logger import logger

# 加载 .env 文件
PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class EmailConfig:
    """邮件配置"""

    # SMTP 配置（从环境变量读取）
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_SECURE: bool = os.getenv("SMTP_SECURE", "false").lower() == "true"

    # 收件人
    NOTIFY_EMAIL: str = os.getenv("NOTIFY_EMAIL", "")

    @classmethod
    def is_configured(cls) -> bool:
        """检查 SMTP 发件配置是否完整"""
        return all([
            cls.SMTP_HOST,
            cls.SMTP_USER,
            cls.SMTP_PASSWORD,
        ])


# Jinja2 模板环境
template_dir = os.path.join(os.path.dirname(__file__), "templates")
if not os.path.exists(template_dir):
    os.makedirs(template_dir)

jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(["html", "xml"]),
)


def get_importance_emoji(importance: str) -> str:
    """获取重要程度对应的表情符号"""
    emoji_map = {
        "urgent": "🚨",
        "high": "🔥",
        "medium": "⚡",
        "low": "📌",
    }
    return emoji_map.get(importance, "📌")


def render_email_html(
    hotspots: List[Dict[str, Any]],
    keywords_map: Dict[str, str],
    time_range_start: datetime,
    time_range_end: datetime,
    total_filtered: int = 0,
) -> str:
    """
    渲染邮件 HTML 内容

    Args:
        hotspots: 热点列表
        keywords_map: 关键词ID -> 关键词文本映射
        time_range_start: 时间范围开始
        time_range_end: 时间范围结束
        total_filtered: 筛选总数（超过50条时显示）

    Returns:
        渲染后的 HTML 字符串
    """
    # 按关键词分组
    grouped_hotspots: Dict[str, List[Dict[str, Any]]] = {}
    for hotspot in hotspots:
        keyword_id = hotspot.get("keywordId")
        keyword_text = keywords_map.get(keyword_id, "未知关键词")
        if keyword_text not in grouped_hotspots:
            grouped_hotspots[keyword_text] = []
        grouped_hotspots[keyword_text].append(hotspot)

    # 计算统计信息
    total_count = len(hotspots)
    keyword_count = len(grouped_hotspots)

    # 构建模板数据
    template_data = {
        "total_count": total_count,
        "keyword_count": keyword_count,
        "time_range_start": time_range_start.strftime("%Y-%m-%d %H:%M"),
        "time_range_end": time_range_end.strftime("%Y-%m-%d %H:%M"),
        "grouped_hotspots": grouped_hotspots,
        "get_importance_emoji": get_importance_emoji,
        "total_filtered": total_filtered,
        "max_display": 50,
    }

    # 检查模板文件是否存在
    template_path = os.path.join(template_dir, "hotspot_email.html")
    if os.path.exists(template_path):
        template = jinja_env.get_template("hotspot_email.html")
        return template.render(**template_data)
    else:
        # 使用内置简单模板
        return render_simple_email_html(template_data)


def render_simple_email_html(data: Dict[str, Any]) -> str:
    """渲染简单邮件 HTML（无模板文件时使用）"""
    html_parts = [
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        '<meta charset="utf-8">',
        '<style>',
        'body { font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }',
        '.container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }',
        '.header { border-bottom: 2px solid #eee; padding-bottom: 20px; }',
        '.header h1 { color: #333; margin: 0; }',
        '.summary { background: #f9f9f9; padding: 15px; border-radius: 4px; margin: 20px 0; }',
        '.keyword-section { margin: 20px 0; padding: 15px; border-left: 4px solid #007bff; }',
        '.keyword-title { font-weight: bold; color: #007bff; margin-bottom: 10px; }',
        '.hotspot-item { padding: 10px 0; border-bottom: 1px solid #eee; }',
        '.hotspot-title { font-weight: bold; color: #333; }',
        '.hotspot-meta { color: #666; font-size: 12px; }',
        '.badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; }',
        '.badge-urgent { background: #dc3545; color: white; }',
        '.badge-high { background: #fd7e14; color: white; }',
        '.badge-medium { background: #ffc107; color: #333; }',
        '.badge-low { background: #28a745; color: white; }',
        '.link { color: #007bff; text-decoration: none; }',
        '.footer { margin-top: 20px; padding-top: 20px; border-top: 2px solid #eee; color: #666; }',
        '</style>',
        '</head>',
        '<body>',
        '<div class="container">',
        '<div class="header">',
        f'<h1>📊 AI热点监控 - 您有 {data["total_count"]} 条重要热点待查看</h1>',
        '</div>',
        '<div class="summary">',
        f'<p>共 <strong>{data["total_count"]}</strong> 条重要热点 | 涉及 <strong>{data["keyword_count"]}</strong> 个关键词</p>',
        f'<p>时间范围：{data["time_range_start"]} ~ {data["time_range_end"]}</p>',
        '</div>',
    ]

    for keyword_text, hotspots in data["grouped_hotspots"].items():
        html_parts.append(f'<div class="keyword-section">')
        html_parts.append(f'<div class="keyword-title">🔍 关键词：{keyword_text}</div>')
        html_parts.append(f'<p>该关键词下 {len(hotspots)} 条热点</p>')

        for hotspot in hotspots:
            importance = hotspot.get("importance", "low")
            emoji = data["get_importance_emoji"](importance)
            title = hotspot.get("title", "")[:80]
            source = hotspot.get("source", "")
            summary = hotspot.get("summary", "")
            url = hotspot.get("url", "")

            html_parts.append('<div class="hotspot-item">')
            html_parts.append(f'<div class="hotspot-title">{emoji} [{importance.upper()}] {title}</div>')
            html_parts.append(f'<div class="hotspot-meta">来源：{source}</div>')
            if summary:
                html_parts.append(f'<p>{summary[:200]}</p>')
            if url:
                html_parts.append(f'<a class="link" href="{url}">查看原文 →</a>')
            html_parts.append('</div>')

        html_parts.append('</div>')

    if data["total_filtered"] > data["max_display"]:
        html_parts.append('<div class="footer">')
        html_parts.append(f'<p>💡 共筛选 {data["total_filtered"]} 条热点，已发送前 {data["max_display"]} 条</p>')
        html_parts.append('<p>请前往 Dashboard 查看完整列表</p>')
        html_parts.append('</div>')

    html_parts.append('</div>')
    html_parts.append('</body>')
    html_parts.append('</html>')

    return "\n".join(html_parts)


async def send_email(
    subject: str,
    html_content: str,
    to_email: Optional[str] = None,
) -> bool:
    """
    发送邮件

    Args:
        subject: 邮件主题
        html_content: HTML 内容
        to_email: 收件人（可选，默认使用配置）

    Returns:
        是否发送成功
    """
    if not EmailConfig.is_configured():
        logger.warning("邮件配置不完整，无法发送邮件")
        return False

    recipient = to_email or EmailConfig.NOTIFY_EMAIL

    try:
        # 构建邮件
        message = MIMEMultipart("alternative")
        message["From"] = EmailConfig.SMTP_USER
        message["To"] = recipient
        message["Subject"] = subject

        # 添加 HTML 内容
        html_part = MIMEText(html_content, "html", "utf-8")
        message.attach(html_part)

        # 发送邮件
        # 465 端口使用 SSL，587 端口使用 STARTTLS
        use_tls = EmailConfig.SMTP_SECURE  # SMTP_SECURE=true 表示使用 SSL (465端口)
        start_tls = not EmailConfig.SMTP_SECURE  # SMTP_SECURE=false 表示使用 STARTTLS (587端口)

        await aiosmtplib.send(
            message,
            hostname=EmailConfig.SMTP_HOST,
            port=EmailConfig.SMTP_PORT,
            username=EmailConfig.SMTP_USER,
            password=EmailConfig.SMTP_PASSWORD,
            use_tls=use_tls,
            start_tls=start_tls,
        )

        logger.info(f"邮件已发送至 {recipient}")
        return True

    except Exception as e:
        logger.error(f"邮件发送失败: {e}")
        return False


async def send_hotspot_email(
    db: AsyncSession,
    hotspots: List[Hotspot],
    hours: int = 24,
    user_id: str = None,
) -> bool:
    """
    发送热点邮件通知

    SMTP 配置从 .env 读取，收件邮箱从数据库 app_settings 读取

    Args:
        db: 数据库会话
        hotspots: 热点列表
        hours: 时间范围（用于显示）
        user_id: 用户 ID

    Returns:
        是否发送成功
    """
    if not hotspots:
        logger.info("无热点需要发送邮件")
        return False

    # 从数据库读取收件邮箱
    from backend.services.settings_service import get_settings
    recipient_email = None
    try:
        settings = await get_settings(user_id)
        recipient_email = settings.get("notifyEmail")
    except Exception:
        pass

    if not EmailConfig.is_configured():
        logger.warning("邮件配置不完整，无法发送邮件")
        return False

    if not recipient_email:
        logger.warning(f"用户 {user_id} 未配置收件邮箱，跳过邮件发送")
        return False

    # 获取关键词映射
    keyword_ids = [h.keywordId for h in hotspots if h.keywordId]
    keywords_map: Dict[str, str] = {}

    if keyword_ids:
        result = await db.execute(select(Keyword).where(Keyword.id.in_(keyword_ids)))
        keywords = result.scalars().all()
        keywords_map = {k.id: k.text for k in keywords}

    # 转换热点数据
    hotspot_data = []
    for h in hotspots:
        hotspot_data.append({
            "id": h.id,
            "title": h.title,
            "importance": h.importance,
            "source": h.source,
            "summary": h.summary,
            "url": h.url,
            "keywordId": h.keywordId,
        })

    # 时间范围
    time_range_end = datetime.now()
    time_range_start = time_range_end - timedelta(hours=hours)

    # 渲染邮件
    subject = f"【AI热点监控】您有 {len(hotspots)} 条重要热点待查看"
    html_content = render_email_html(
        hotspots=hotspot_data,
        keywords_map=keywords_map,
        time_range_start=time_range_start,
        time_range_end=time_range_end,
    )

    # 发送邮件
    success = await send_email(subject, html_content, to_email=recipient_email)

    if success:
        # 更新邮件发送状态
        hotspot_ids = [h.id for h in hotspots]
        await db.execute(
            update(Hotspot)
            .where(Hotspot.id.in_(hotspot_ids))
            .values(emailSent=True, emailSentAt=datetime.now())
        )
        await db.commit()
        logger.info(f"已更新 {len(hotspots)} 条热点的邮件发送状态")

    return success