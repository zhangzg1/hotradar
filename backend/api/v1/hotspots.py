"""
热点接口
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, desc, asc, or_, and_, text, delete
from sqlalchemy.exc import IntegrityError
from typing import Optional, List
from datetime import datetime, timedelta

from backend.common.mysql import get_async_db
from backend.common.auth import get_current_user
from backend.models import Hotspot, ChatSession, ChatMessage
from backend.schemas.request import HotspotSearchRequest
from backend.schemas.response import (
    HotspotResponse,
    HotspotListResponse,
    HotspotDetailResponse,
    HotspotStatsResponse,
    AuthorInfo,
    EngagementStats,
    SourceDistribution,
    ImportanceDistribution,
    ErrorResponse,
)
from backend.common.logger import logger

router = APIRouter()


@router.get(
    "",
    response_model=HotspotListResponse,
    summary="获取热点列表",
    description="分页获取热点，支持按关键词、来源、重要程度、真假等筛选和排序",
)
async def list_hotspots(
    keyword_ids: Optional[List[str]] = Query(None, description="关键词 ID 筛选"),
    sources: Optional[List[str]] = Query(None, description="来源平台筛选"),
    importance: Optional[List[str]] = Query(None, description="重要程度筛选：low/medium/high/urgent"),
    is_real: Optional[bool] = Query(None, description="真假筛选"),
    email_sent: Optional[bool] = Query(None, description="邮件状态筛选"),
    time_range: Optional[str] = Query(None, description="时间范围：12h/24h/7d/14d"),
    published_at_from: Optional[datetime] = Query(None, description="发布时间起始"),
    published_at_to: Optional[datetime] = Query(None, description="发布时间结束"),
    sort_by: str = Query("createdAt", description="排序字段：createdAt/publishedAt/importance/relevance"),
    sort_order: str = Query("desc", description="排序方向：asc/desc"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """获取热点列表"""
    # 构建查询
    query = select(Hotspot).where(Hotspot.userId == current_user)

    # 筛选条件
    conditions = []
    if keyword_ids:
        conditions.append(Hotspot.keywordId.in_(keyword_ids))
    if sources:
        conditions.append(Hotspot.source.in_(sources))
    if importance:
        conditions.append(Hotspot.importance.in_(importance))
    if is_real is not None:
        conditions.append(Hotspot.isReal == is_real)
    if email_sent is not None:
        conditions.append(Hotspot.emailSent == email_sent)

    # 时间范围筛选
    if time_range:
        now = datetime.now()
        if time_range == '12h':
            conditions.append(Hotspot.createdAt >= now - timedelta(hours=12))
        elif time_range == '24h':
            conditions.append(Hotspot.createdAt >= now - timedelta(hours=24))
        elif time_range == '7d':
            conditions.append(Hotspot.createdAt >= now - timedelta(days=7))
        elif time_range == '14d':
            conditions.append(Hotspot.createdAt >= now - timedelta(days=14))

    if published_at_from:
        conditions.append(Hotspot.publishedAt >= published_at_from)
    if published_at_to:
        conditions.append(Hotspot.publishedAt <= published_at_to)

    if conditions:
        query = query.where(and_(*conditions))

    # 计算总数
    count_query = select(func.count(Hotspot.id)).where(Hotspot.userId == current_user)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 排序
    if sort_by == "publishedAt":
        # 发布时间排序：NULL 值排在最后
        # MySQL 使用 ISNULL 函数让 NULL 值排在最后
        if sort_order == "desc":
            query = query.order_by(text("ISNULL(publishedAt)"), desc(Hotspot.publishedAt))
        else:
            query = query.order_by(text("ISNULL(publishedAt)"), asc(Hotspot.publishedAt))
    elif sort_by == "importance":
        # 重要程度排序：urgent > high > medium > low
        # 使用 MySQL CASE 语句实现自定义排序
        importance_case = text("""
            CASE importance
                WHEN 'urgent' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
                ELSE 5
            END
        """)
        if sort_order == "desc":
            query = query.order_by(importance_case)
        else:
            query = query.order_by(text("""
                CASE importance
                    WHEN 'urgent' THEN 5
                    WHEN 'high' THEN 4
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 2
                    ELSE 1
                END
            """))
    elif sort_by == "relevance":
        if sort_order == "desc":
            query = query.order_by(desc(Hotspot.relevance))
        else:
            query = query.order_by(asc(Hotspot.relevance))
    else:
        # 默认按抓取时间排序
        if sort_order == "desc":
            query = query.order_by(desc(Hotspot.createdAt))
        else:
            query = query.order_by(asc(Hotspot.createdAt))

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    hotspots = result.scalars().all()

    # 构建响应
    hotspots_data = [
        HotspotResponse(
            id=h.id,
            title=h.title,
            content=h.content[:200] if len(h.content) > 200 else h.content,
            url=h.url,
            source=h.source,
            isReal=h.isReal,
            relevance=h.relevance,
            importance=h.importance,
            summary=h.summary,
            publishedAt=h.publishedAt,
            createdAt=h.createdAt,
            keywordId=h.keywordId,
        )
        for h in hotspots
    ]

    return HotspotListResponse(
        data=hotspots_data,
        total=total,
        page=page,
        pageSize=page_size,
    )


@router.get(
    "/stats",
    response_model=HotspotStatsResponse,
    summary="获取热点统计",
    description="获取热点统计概览：总数、今日新增、本周新增、各级别数量、各来源分布",
)
async def get_hotspot_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """获取热点统计"""
    user_filter = Hotspot.userId == current_user

    # 总数
    total_result = await db.execute(
        select(func.count(Hotspot.id)).where(user_filter)
    )
    total = total_result.scalar()

    # 今日新增
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await db.execute(
        select(func.count(Hotspot.id)).where(Hotspot.createdAt >= today_start, user_filter)
    )
    today_new = today_result.scalar()

    # 本周新增（周一开始）
    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_result = await db.execute(
        select(func.count(Hotspot.id)).where(Hotspot.createdAt >= week_start, user_filter)
    )
    week_new = week_result.scalar()

    # 重要程度分布
    importance_result = await db.execute(
        select(Hotspot.importance, func.count(Hotspot.id))
        .where(user_filter)
        .group_by(Hotspot.importance)
    )
    importance_rows = importance_result.all()
    importance_distribution = [
        ImportanceDistribution(importance=row[0] or "unknown", count=row[1])
        for row in importance_rows
    ]

    # 来源分布
    source_result = await db.execute(
        select(Hotspot.source, func.count(Hotspot.id))
        .where(user_filter)
        .group_by(Hotspot.source)
        .order_by(desc(func.count(Hotspot.id)))
    )
    source_rows = source_result.all()
    source_distribution = [
        SourceDistribution(source=row[0], count=row[1])
        for row in source_rows
    ]

    # 真假统计
    real_result = await db.execute(
        select(func.count(Hotspot.id)).where(Hotspot.isReal == True, user_filter)
    )
    real_count = real_result.scalar()

    fake_result = await db.execute(
        select(func.count(Hotspot.id)).where(Hotspot.isReal == False, user_filter)
    )
    fake_count = fake_result.scalar()

    # 邮件通知统计
    email_result = await db.execute(
        select(func.count(Hotspot.id)).where(Hotspot.emailSent == True, user_filter)
    )
    emailed_count = email_result.scalar()

    return HotspotStatsResponse(
        total=total,
        todayNew=today_new,
        weekNew=week_new,
        importanceDistribution=importance_distribution,
        sourceDistribution=source_distribution,
        realCount=real_count,
        fakeCount=fake_count,
        emailedCount=emailed_count,
    )


@router.get(
    "/{hotspot_id}",
    response_model=HotspotDetailResponse,
    responses={404: {"model": ErrorResponse}},
    summary="获取热点详情",
    description="获取单个热点的完整信息",
)
async def get_hotspot_detail(
    hotspot_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """获取热点详情"""
    result = await db.execute(
        select(Hotspot).where(Hotspot.id == hotspot_id, Hotspot.userId == current_user)
    )
    hotspot = result.scalar_one_or_none()

    if not hotspot:
        raise HTTPException(status_code=404, detail="热点不存在")

    return HotspotDetailResponse(
        id=hotspot.id,
        title=hotspot.title,
        content=hotspot.content,
        url=hotspot.url,
        source=hotspot.source,
        sourceId=hotspot.sourceId,
        isReal=hotspot.isReal,
        relevance=hotspot.relevance,
        relevanceReason=hotspot.relevanceReason,
        keywordMentioned=hotspot.keywordMentioned,
        importance=hotspot.importance,
        summary=hotspot.summary,
        author=AuthorInfo(
            name=hotspot.authorName,
            username=hotspot.authorUsername,
            avatar=hotspot.authorAvatar,
            followers=hotspot.authorFollowers,
            verified=hotspot.authorVerified,
        ),
        engagement=EngagementStats(
            viewCount=hotspot.viewCount,
            likeCount=hotspot.likeCount,
            retweetCount=hotspot.retweetCount,
            replyCount=hotspot.replyCount,
            commentCount=hotspot.commentCount,
            quoteCount=hotspot.quoteCount,
            danmakuCount=hotspot.danmakuCount,
        ),
        emailSent=hotspot.emailSent,
        emailSentAt=hotspot.emailSentAt,
        publishedAt=hotspot.publishedAt,
        createdAt=hotspot.createdAt,
        keywordId=hotspot.keywordId,
    )


@router.post(
    "/search",
    response_model=HotspotListResponse,
    summary="搜索热点",
    description="根据特定内容搜索热点（标题、内容、摘要模糊匹配）",
)
async def search_hotspots(
    request: HotspotSearchRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """搜索热点"""
    # 构建搜索条件
    search_pattern = f"%{request.query}%"
    search_condition = or_(
        Hotspot.title.ilike(search_pattern),
        Hotspot.content.ilike(search_pattern),
        Hotspot.summary.ilike(search_pattern),
    )

    # 其他筛选条件
    conditions = [search_condition, Hotspot.userId == current_user]
    if request.keywordId:
        conditions.append(Hotspot.keywordId == request.keywordId)
    if request.source:
        conditions.append(Hotspot.source == request.source)
    if request.importance:
        conditions.append(Hotspot.importance.in_(request.importance))
    if request.isReal is not None:
        conditions.append(Hotspot.isReal == request.isReal)
    if request.publishedAtFrom:
        conditions.append(Hotspot.publishedAt >= request.publishedAtFrom)
    if request.publishedAtTo:
        conditions.append(Hotspot.publishedAt <= request.publishedAtTo)

    # 查询
    query = select(Hotspot).where(and_(*conditions)).order_by(desc(Hotspot.createdAt))

    # 计算总数
    count_query = select(func.count(Hotspot.id)).where(and_(*conditions))
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 分页
    query = query.offset(request.offset).limit(request.limit)

    result = await db.execute(query)
    hotspots = result.scalars().all()

    # 构建响应
    hotspots_data = [
        HotspotResponse(
            id=h.id,
            title=h.title,
            content=h.content[:200] if len(h.content) > 200 else h.content,
            url=h.url,
            source=h.source,
            isReal=h.isReal,
            relevance=h.relevance,
            importance=h.importance,
            summary=h.summary,
            publishedAt=h.publishedAt,
            createdAt=h.createdAt,
            keywordId=h.keywordId,
        )
        for h in hotspots
    ]

    page = (request.offset // request.limit) + 1 if request.limit > 0 else 1

    return HotspotListResponse(
        data=hotspots_data,
        total=total,
        page=page,
        pageSize=request.limit,
    )


@router.delete(
    "/{hotspot_id}",
    summary="删除热点",
    description="删除单个热点及其关联的聊天会话",
)
async def delete_hotspot(
    hotspot_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """删除热点"""
    result = await db.execute(
        select(Hotspot).where(Hotspot.id == hotspot_id, Hotspot.userId == current_user)
    )
    hotspot = result.scalar_one_or_none()

    if not hotspot:
        raise HTTPException(status_code=404, detail="热点不存在")

    # 先获取该热点的所有聊天会话ID
    session_result = await db.execute(
        select(ChatSession.id).where(ChatSession.hotspotId == hotspot_id)
    )
    session_ids = [row[0] for row in session_result.all()]

    # 删除聊天消息
    if session_ids:
        await db.execute(delete(ChatMessage).where(ChatMessage.sessionId.in_(session_ids)))
        logger.info(f"删除热点 {hotspot_id}: 已删除 {len(session_ids)} 个聊天会话的消息")

    # 删除聊天会话
    await db.execute(delete(ChatSession).where(ChatSession.hotspotId == hotspot_id))

    # 删除热点
    await db.delete(hotspot)
    await db.commit()

    logger.info(f"热点已删除：{hotspot_id}，已清除关联聊天数据")

    return {"message": "热点已删除", "id": hotspot_id}
