"""
关键词接口
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, desc, asc, or_, delete
from sqlalchemy.exc import IntegrityError
from typing import Optional
import uuid

from backend.common.mysql import get_async_db
from backend.common.auth import get_current_user
from backend.models import Keyword, Hotspot, ChatSession, ChatMessage
from backend.schemas.request import (
    KeywordCreateRequest,
    KeywordUpdateRequest,
    KeywordBatchRequest,
    BatchAction,
)
from backend.schemas.response import (
    KeywordListResponse,
    KeywordDetailResponse,
    KeywordStatsResponse,
    CategoryStats,
    ErrorResponse,
)
from backend.common.logger import logger

router = APIRouter()


@router.get(
    "",
    response_model=KeywordListResponse,
    summary="获取关键词列表",
    description="分页获取关键词列表，支持按状态筛选和排序，返回每个关键词的热点数量",
)
async def list_keywords(
    is_active: Optional[bool] = Query(None, description="激活状态筛选"),
    category: Optional[str] = Query(None, description="分类筛选"),
    sort_by: str = Query("createdAt", description="排序字段: createdAt/updatedAt/hotspotCount"),
    sort_order: str = Query("desc", description="排序方向: asc/desc"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """获取关键词列表"""
    # 构建基础查询（包含热点数量统计）
    hotspot_count = func.count(Hotspot.id).label("hotspotCount")

    query = (
        select(Keyword, hotspot_count)
        .outerjoin(Hotspot, Keyword.id == Hotspot.keywordId)
        .where(Keyword.userId == current_user)
        .group_by(Keyword.id)
    )

    # 筛选条件
    if is_active is not None:
        query = query.where(Keyword.isActive == is_active)
    if category:
        query = query.where(Keyword.category == category)

    # 计算总数
    count_query = select(func.count(Keyword.id)).where(Keyword.userId == current_user)
    if is_active is not None:
        count_query = count_query.where(Keyword.isActive == is_active)
    if category:
        count_query = count_query.where(Keyword.category == category)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 排序
    order_func = desc if sort_order == "desc" else asc
    if sort_by == "hotspotCount":
        query = query.order_by(order_func(hotspot_count))
    elif sort_by == "updatedAt":
        query = query.order_by(order_func(Keyword.updatedAt))
    else:
        query = query.order_by(order_func(Keyword.createdAt))

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    # 构建响应
    keywords_data = []
    for row in rows:
        keyword = row[0]
        count = row[1]
        keywords_data.append(
            KeywordDetailResponse(
                id=keyword.id,
                text=keyword.text,
                category=keyword.category,
                isActive=keyword.isActive,
                createdAt=keyword.createdAt,
                updatedAt=keyword.updatedAt,
                hotspotCount=count,
                recentHotspots=[],
            )
        )

    return KeywordListResponse(
        data=keywords_data,
        total=total,
        page=page,
        pageSize=page_size,
    )


@router.get(
    "/stats",
    response_model=KeywordStatsResponse,
    summary="获取关键词统计",
    description="获取关键词总数、活跃数、各分类数量统计",
)
async def get_keyword_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """获取关键词统计"""
    # 总数
    total_result = await db.execute(
        select(func.count(Keyword.id)).where(Keyword.userId == current_user)
    )
    total = total_result.scalar()

    # 活跃数
    active_result = await db.execute(
        select(func.count(Keyword.id)).where(Keyword.isActive == True, Keyword.userId == current_user)
    )
    active = active_result.scalar()

    # 分类统计
    category_result = await db.execute(
        select(Keyword.category, func.count(Keyword.id))
        .where(Keyword.userId == current_user)
        .group_by(Keyword.category)
        .order_by(desc(func.count(Keyword.id)))
    )
    category_rows = category_result.all()

    categories = [
        CategoryStats(category=row[0], count=row[1])
        for row in category_rows
        if row[0] is not None
    ]

    return KeywordStatsResponse(
        total=total,
        active=active,
        inactive=total - active,
        categories=categories,
    )


@router.get(
    "/{keyword_id}",
    response_model=KeywordDetailResponse,
    responses={404: {"model": ErrorResponse}},
    summary="获取关键词详情",
    description="获取单个关键词的完整信息，包含最近热点",
)
async def get_keyword_detail(
    keyword_id: str,
    hotspot_limit: int = Query(5, ge=0, le=20, description="返回最近热点数量"),
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """获取关键词详情"""
    # 查询关键词
    result = await db.execute(
        select(Keyword).where(Keyword.id == keyword_id, Keyword.userId == current_user)
    )
    keyword = result.scalar_one_or_none()

    if not keyword:
        raise HTTPException(status_code=404, detail="关键词不存在")

    # 查询热点数量
    count_result = await db.execute(
        select(func.count(Hotspot.id)).where(Hotspot.keywordId == keyword_id)
    )
    hotspot_count = count_result.scalar()

    # 查询最近热点
    recent_result = await db.execute(
        select(Hotspot)
        .where(Hotspot.keywordId == keyword_id)
        .order_by(desc(Hotspot.createdAt))
        .limit(hotspot_limit)
    )
    recent_hotspots = recent_result.scalars().all()

    recent_hotspots_data = [
        {
            "id": h.id,
            "title": h.title[:50] if h.title else None,
            "source": h.source,
            "importance": h.importance,
            "createdAt": h.createdAt,
        }
        for h in recent_hotspots
    ]

    return KeywordDetailResponse(
        id=keyword.id,
        text=keyword.text,
        category=keyword.category,
        isActive=keyword.isActive,
        createdAt=keyword.createdAt,
        updatedAt=keyword.updatedAt,
        hotspotCount=hotspot_count,
        recentHotspots=recent_hotspots_data,
    )


@router.post(
    "",
    response_model=KeywordDetailResponse,
    responses={409: {"model": ErrorResponse}},
    summary="创建关键词",
    description="创建新关键词，text必须唯一",
)
async def create_keyword(
    request: KeywordCreateRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """创建关键词"""
    new_keyword = Keyword(
        id=str(uuid.uuid4()),
        text=request.text,
        category=request.category,
        isActive=True,
        userId=current_user,
    )

    db.add(new_keyword)

    try:
        await db.commit()
        await db.refresh(new_keyword)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"关键词 '{request.text}' 已存在")

    logger.info(f"关键词已创建: {new_keyword.id} - {new_keyword.text}")

    return KeywordDetailResponse(
        id=new_keyword.id,
        text=new_keyword.text,
        category=new_keyword.category,
        isActive=new_keyword.isActive,
        createdAt=new_keyword.createdAt,
        updatedAt=new_keyword.updatedAt,
        hotspotCount=0,
        recentHotspots=[],
    )


@router.put(
    "/{keyword_id}",
    response_model=KeywordDetailResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    summary="更新关键词",
    description="更新关键词的text或category",
)
async def update_keyword(
    keyword_id: str,
    request: KeywordUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """更新关键词"""
    result = await db.execute(
        select(Keyword).where(Keyword.id == keyword_id, Keyword.userId == current_user)
    )
    keyword = result.scalar_one_or_none()

    if not keyword:
        raise HTTPException(status_code=404, detail="关键词不存在")

    if request.text:
        keyword.text = request.text
    if request.category:
        keyword.category = request.category

    try:
        await db.commit()
        await db.refresh(keyword)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"关键词 '{request.text}' 已存在")

    # 查询热点数量
    count_result = await db.execute(
        select(func.count(Hotspot.id)).where(Hotspot.keywordId == keyword_id)
    )
    hotspot_count = count_result.scalar()

    return KeywordDetailResponse(
        id=keyword.id,
        text=keyword.text,
        category=keyword.category,
        isActive=keyword.isActive,
        createdAt=keyword.createdAt,
        updatedAt=keyword.updatedAt,
        hotspotCount=hotspot_count,
        recentHotspots=[],
    )


@router.patch(
    "/{keyword_id}/toggle",
    response_model=KeywordDetailResponse,
    responses={404: {"model": ErrorResponse}},
    summary="激活/暂停关键词",
    description="切换关键词的激活状态",
)
async def toggle_keyword(
    keyword_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """激活/暂停关键词"""
    result = await db.execute(
        select(Keyword).where(Keyword.id == keyword_id, Keyword.userId == current_user)
    )
    keyword = result.scalar_one_or_none()

    if not keyword:
        raise HTTPException(status_code=404, detail="关键词不存在")

    keyword.isActive = not keyword.isActive
    await db.commit()
    await db.refresh(keyword)

    # 查询热点数量
    count_result = await db.execute(
        select(func.count(Hotspot.id)).where(Hotspot.keywordId == keyword_id)
    )
    hotspot_count = count_result.scalar()

    logger.info(f"关键词状态已切换: {keyword.id} - isActive={keyword.isActive}")

    return KeywordDetailResponse(
        id=keyword.id,
        text=keyword.text,
        category=keyword.category,
        isActive=keyword.isActive,
        createdAt=keyword.createdAt,
        updatedAt=keyword.updatedAt,
        hotspotCount=hotspot_count,
        recentHotspots=[],
    )


@router.delete(
    "/{keyword_id}",
    summary="删除关键词",
    description="删除关键词及其关联的所有热点数据和聊天会话",
)
async def delete_keyword(
    keyword_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """删除关键词"""
    result = await db.execute(
        select(Keyword).where(Keyword.id == keyword_id, Keyword.userId == current_user)
    )
    keyword = result.scalar_one_or_none()

    if not keyword:
        raise HTTPException(status_code=404, detail="关键词不存在")

    # 获取所有关联的热点ID
    hotspot_result = await db.execute(
        select(Hotspot.id).where(Hotspot.keywordId == keyword_id)
    )
    hotspot_ids = [row[0] for row in hotspot_result.all()]

    # 删除关联热点的所有聊天消息
    if hotspot_ids:
        # 先获取所有聊天会话ID
        session_result = await db.execute(
            select(ChatSession.id).where(ChatSession.hotspotId.in_(hotspot_ids))
        )
        session_ids = [row[0] for row in session_result.all()]

        # 删除聊天消息
        if session_ids:
            await db.execute(delete(ChatMessage).where(ChatMessage.sessionId.in_(session_ids)))
            logger.info(f"删除关键词 {keyword_id}: 已删除 {len(session_ids)} 个聊天会话的消息")

        # 删除聊天会话
        await db.execute(delete(ChatSession).where(ChatSession.hotspotId.in_(hotspot_ids)))
        logger.info(f"删除关键词 {keyword_id}: 已删除 {len(hotspot_ids)} 个热点的聊天会话")

    # 删除关联的所有热点数据
    await db.execute(delete(Hotspot).where(Hotspot.keywordId == keyword_id))

    # 删除关键词
    await db.delete(keyword)
    await db.commit()

    logger.info(f"关键词已删除: {keyword_id}，已清除关联热点数据")

    return {"message": "关键词已删除", "id": keyword_id}


@router.post(
    "/batch",
    summary="批量操作",
    description="批量激活、暂停或删除关键词",
)
async def batch_operation(
    request: KeywordBatchRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """批量操作关键词"""
    # 验证关键词是否存在
    result = await db.execute(
        select(Keyword).where(Keyword.id.in_(request.keywordIds), Keyword.userId == current_user)
    )
    keywords = result.scalars().all()

    if not keywords:
        raise HTTPException(status_code=404, detail="未找到任何关键词")

    found_ids = [k.id for k in keywords]
    missing_ids = [id for id in request.keywordIds if id not in found_ids]

    affected_count = 0

    if request.action == BatchAction.activate:
        await db.execute(
            update(Keyword)
            .where(Keyword.id.in_(found_ids))
            .values(isActive=True)
        )
        affected_count = len(found_ids)

    elif request.action == BatchAction.deactivate:
        await db.execute(
            update(Keyword)
            .where(Keyword.id.in_(found_ids))
            .values(isActive=False)
        )
        affected_count = len(found_ids)

    elif request.action == BatchAction.delete:
        # 获取所有关联的热点ID
        hotspot_result = await db.execute(
            select(Hotspot.id).where(Hotspot.keywordId.in_(found_ids))
        )
        hotspot_ids = [row[0] for row in hotspot_result.all()]

        # 删除关联热点的所有聊天消息和会话
        if hotspot_ids:
            session_result = await db.execute(
                select(ChatSession.id).where(ChatSession.hotspotId.in_(hotspot_ids))
            )
            session_ids = [row[0] for row in session_result.all()]

            if session_ids:
                await db.execute(delete(ChatMessage).where(ChatMessage.sessionId.in_(session_ids)))

            await db.execute(delete(ChatSession).where(ChatSession.hotspotId.in_(hotspot_ids)))

        # 删除热点
        await db.execute(delete(Hotspot).where(Hotspot.keywordId.in_(found_ids)))
        # 删除关键词
        await db.execute(delete(Keyword).where(Keyword.id.in_(found_ids)))
        affected_count = len(found_ids)

    await db.commit()

    logger.info(f"批量操作完成: action={request.action}, affected={affected_count}")

    return {
        "message": f"批量{request.action}完成",
        "affectedCount": affected_count,
        "missingIds": missing_ids,
    }
