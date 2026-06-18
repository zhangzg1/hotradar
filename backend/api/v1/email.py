"""
邮件通知接口
POST /email-notifications - 创建邮件通知任务
POST /email-notifications/send-recent - 发送最近时间范围内的热点（主动推送）
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from datetime import datetime, timedelta

from backend.common.mysql import get_async_db
from backend.common.auth import get_current_user
from backend.models import Hotspot
from backend.schemas.request import EmailNotificationRequest
from backend.schemas.response import EmailNotificationResponse
from backend.services.email_service import send_hotspot_email, EmailConfig
from backend.services.settings_service import is_email_valid
from backend.common.logger import logger


router = APIRouter()


# 时间范围映射
TIME_RANGE_MAP = {
    "1h": 1,
    "6h": 6,
    "24h": 24,
    "7d": 168,
}


@router.post(
    "/send-recent",
    response_model=EmailNotificationResponse,
    summary="发送最近热点",
    description="主动推送最近时间范围内的热点（不限制是否已发送）",
)
async def send_recent_hotspots(
    request: dict = {"timeRange": "24h"},
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """
    主动邮件推送最近时间范围内的热点

    Args:
        timeRange: 时间范围 (1h/6h/24h/7d)
    """
    if not EmailConfig.is_configured():
        raise HTTPException(status_code=503, detail="邮件配置不完整，请检查 .env 中的 SMTP 配置")

    if not await is_email_valid(current_user):
        raise HTTPException(status_code=503, detail="请先在设置中配置有效的收件邮箱")

    timeRange = request.get("timeRange", "24h")

    hours = TIME_RANGE_MAP.get(timeRange, 24)
    time_threshold = datetime.now() - timedelta(hours=hours)

    # 查询最近时间范围内的热点（重要程度为 high 或 urgent）
    conditions = [
        Hotspot.importance.in_(["high", "urgent"]),
        Hotspot.createdAt >= time_threshold,
        Hotspot.userId == current_user,
    ]

    query = (
        select(Hotspot)
        .where(and_(*conditions))
        .order_by(desc(Hotspot.importance), desc(Hotspot.createdAt))
        .limit(50)
    )

    result = await db.execute(query)
    hotspots = result.scalars().all()

    if not hotspots:
        return EmailNotificationResponse(
            sentCount=0,
            hotspots=[],
            message=f"最近 {hours} 小时内无重要热点",
        )

    # 发送邮件
    success = await send_hotspot_email(db, list(hotspots), hours, user_id=current_user)

    if not success:
        raise HTTPException(status_code=500, detail="邮件发送失败")

    brief_hotspots = [
        {
            "id": h.id,
            "title": h.title[:50],
            "importance": h.importance,
            "source": h.source,
        }
        for h in hotspots
    ]

    logger.info(f"邮件推送已发送: {len(hotspots)} 条热点 (时间范围: {timeRange})")

    return EmailNotificationResponse(
        sentCount=len(hotspots),
        hotspots=brief_hotspots,
        message="邮件已发送",
    )


@router.post(
    "",
    response_model=EmailNotificationResponse,
    summary="创建邮件通知",
    description="发送未邮件通知的重要热点到用户邮箱",
)
async def create_email_notification(
    request: EmailNotificationRequest = EmailNotificationRequest(),
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """
    创建邮件通知任务

    发送未邮件通知的重要热点到用户邮箱

    Args:
        hours: 时间范围（默认24小时，最大168小时即7天）
        importance: 级别筛选（默认 ["high", "urgent"]）
        keywordIds: 关键词ID筛选（可选，默认全部）
    """
    if not EmailConfig.is_configured():
        raise HTTPException(status_code=503, detail="邮件配置不完整，请检查 .env 中的 SMTP 配置")

    if not await is_email_valid(current_user):
        raise HTTPException(status_code=503, detail="请先在设置中配置有效的收件邮箱")

    # 构建查询条件
    time_threshold = datetime.now() - timedelta(hours=request.hours)

    conditions = [
        Hotspot.emailSent == False,
        Hotspot.importance.in_(request.importance),
        Hotspot.createdAt >= time_threshold,
        Hotspot.userId == current_user,
    ]

    if request.keywordIds:
        conditions.append(Hotspot.keywordId.in_(request.keywordIds))

    # 查询热点（最多50条）
    query = (
        select(Hotspot)
        .where(and_(*conditions))
        .order_by(desc(Hotspot.importance), desc(Hotspot.createdAt))
        .limit(50)
    )

    result = await db.execute(query)
    hotspots = result.scalars().all()

    if not hotspots:
        return EmailNotificationResponse(
            sentCount=0,
            hotspots=[],
            message="无符合条件的热点需要发送",
        )

    # 发送邮件
    success = await send_hotspot_email(db, list(hotspots), request.hours, user_id=current_user)

    if not success:
        raise HTTPException(status_code=500, detail="邮件发送失败")

    # 构建简要热点信息
    brief_hotspots = [
        {
            "id": h.id,
            "title": h.title[:50],
            "importance": h.importance,
            "source": h.source,
        }
        for h in hotspots
    ]

    logger.info(f"邮件通知已发送: {len(hotspots)} 条热点")

    return EmailNotificationResponse(
        sentCount=len(hotspots),
        hotspots=brief_hotspots,
        message="邮件已发送",
    )
