"""
热点问答聊天接口
支持流式输出
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, delete, update
from typing import List, Optional
from pydantic import BaseModel

from backend.common.mysql import get_async_db
from backend.common.auth import get_current_user
from backend.schemas.request import ChatRequest
from backend.schemas.response import (
    ChatResponse,
    ChatMessageResponse,
    ChatSessionResponse,
    ChatSessionListResponse,
    ErrorResponse,
)
from backend.models.chat import ChatSession, ChatMessage
from backend.models.hotspot import Hotspot
from backend.services.chat import process_chat, process_chat_stream
from backend.services.settings_service import is_llm_ready
from backend.common.logger import logger

router = APIRouter()


class RenameSessionRequest(BaseModel):
    """重命名会话请求"""
    name: str


@router.post(
    "/{hotspot_id}/chat",
    response_model=ChatResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="热点问答",
    description="针对指定热点发送消息进行问答，支持Tool Calling加载其他热点",
)
async def chat_hotspot(
    hotspot_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """热点问答"""
    if not await is_llm_ready(current_user):
        raise HTTPException(status_code=503, detail="请先在设置中配置并测试 LLM")

    # 验证热点存在
    result = await db.execute(
        select(Hotspot).where(Hotspot.id == hotspot_id, Hotspot.userId == current_user)
    )
    hotspot = result.scalar_one_or_none()

    if not hotspot:
        raise HTTPException(status_code=404, detail="热点不存在")

    try:
        # 处理聊天
        reply, session_id, loaded_hotspots = await process_chat(
            db=db,
            hotspot_id=hotspot_id,
            message=request.message,
            session_id=request.session_id,
            user_id=current_user,
        )

        return ChatResponse(
            reply=reply,
            session_id=session_id,
            loaded_hotspots=loaded_hotspots,
        )

    except Exception as e:
        logger.error(f"[聊天API] 处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"处理消息失败: {str(e)}")


@router.post(
    "/{hotspot_id}/chat/stream",
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="热点问答（流式输出）",
    description="针对指定热点发送消息进行问答，支持流式输出，实时返回AI回复",
)
async def chat_hotspot_stream(
    hotspot_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """热点问答（流式输出）"""
    if not await is_llm_ready(current_user):
        raise HTTPException(status_code=503, detail="请先在设置中配置并测试 LLM")

    # 验证热点存在
    result = await db.execute(
        select(Hotspot).where(Hotspot.id == hotspot_id, Hotspot.userId == current_user)
    )
    hotspot = result.scalar_one_or_none()

    if not hotspot:
        raise HTTPException(status_code=404, detail="热点不存在")

    # 返回 SSE 流式响应
    return StreamingResponse(
        process_chat_stream(
            db=db,
            hotspot_id=hotspot_id,
            message=request.message,
            session_id=request.session_id,
            user_id=current_user,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/{hotspot_id}/sessions",
    response_model=ChatSessionListResponse,
    responses={404: {"model": ErrorResponse}},
    summary="获取热点的历史会话列表",
    description="获取指定热点的所有聊天会话列表",
)
async def get_hotspot_sessions(
    hotspot_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """获取热点的历史会话列表"""
    # 验证热点存在
    result = await db.execute(
        select(Hotspot).where(Hotspot.id == hotspot_id, Hotspot.userId == current_user)
    )
    hotspot = result.scalar_one_or_none()

    if not hotspot:
        raise HTTPException(status_code=404, detail="热点不存在")

    # 查询会话列表
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.hotspotId == hotspot_id)
        .order_by(desc(ChatSession.updatedAt))
    )
    sessions = result.scalars().all()

    # 构建响应（包含消息数量）
    sessions_data = []
    for session in sessions:
        # 查询消息数量
        count_result = await db.execute(
            select(func.count(ChatMessage.id)).where(ChatMessage.sessionId == session.id)
        )
        message_count = count_result.scalar() or 0

        sessions_data.append(
            ChatSessionResponse(
                id=session.id,
                hotspot_id=session.hotspotId,
                name=session.name,
                created_at=session.createdAt,
                updated_at=session.updatedAt,
                message_count=message_count,
            )
        )

    return ChatSessionListResponse(
        data=sessions_data,
        total=len(sessions_data),
    )


@router.get(
    "/{hotspot_id}/sessions/{session_id}",
    response_model=List[ChatMessageResponse],
    responses={404: {"model": ErrorResponse}},
    summary="获取会话消息历史",
    description="获取指定会话的所有消息",
)
async def get_session_messages(
    hotspot_id: str,
    session_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """获取会话消息历史"""
    # 验证热点存在
    result = await db.execute(
        select(Hotspot).where(Hotspot.id == hotspot_id, Hotspot.userId == current_user)
    )
    hotspot = result.scalar_one_or_none()

    if not hotspot:
        raise HTTPException(status_code=404, detail="热点不存在")

    # 验证会话存在且属于该热点
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.hotspotId == hotspot_id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 查询消息列表
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.sessionId == session_id)
        .order_by(ChatMessage.createdAt)
    )
    messages = result.scalars().all()

    # 构建响应
    import json
    messages_data = [
        ChatMessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            loaded_hotspots=json.loads(msg.loadedHotspots) if msg.loadedHotspots else None,
            created_at=msg.createdAt,
        )
        for msg in messages
    ]

    return messages_data


@router.delete(
    "/{hotspot_id}/sessions/{session_id}",
    responses={404: {"model": ErrorResponse}},
    summary="删除会话",
    description="删除指定的聊天会话及其所有消息",
)
async def delete_session(
    hotspot_id: str,
    session_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """删除会话"""
    # 验证热点存在
    result = await db.execute(
        select(Hotspot).where(Hotspot.id == hotspot_id, Hotspot.userId == current_user)
    )
    hotspot = result.scalar_one_or_none()

    if not hotspot:
        raise HTTPException(status_code=404, detail="热点不存在")

    # 验证会话存在且属于该热点
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.hotspotId == hotspot_id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 删除会话的所有消息
    await db.execute(
        delete(ChatMessage).where(ChatMessage.sessionId == session_id)
    )

    # 删除会话
    await db.execute(
        delete(ChatSession).where(ChatSession.id == session_id)
    )

    await db.commit()
    logger.info(f"[聊天API] 删除会话: {session_id}")

    return {"message": "会话已删除"}


@router.patch(
    "/{hotspot_id}/sessions/{session_id}",
    response_model=ChatSessionResponse,
    responses={404: {"model": ErrorResponse}},
    summary="重命名会话",
    description="修改会话的名称",
)
async def rename_session(
    hotspot_id: str,
    session_id: str,
    request: RenameSessionRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """重命名会话"""
    # 验证热点存在
    result = await db.execute(
        select(Hotspot).where(Hotspot.id == hotspot_id, Hotspot.userId == current_user)
    )
    hotspot = result.scalar_one_or_none()

    if not hotspot:
        raise HTTPException(status_code=404, detail="热点不存在")

    # 验证会话存在且属于该热点
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.hotspotId == hotspot_id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 更新名称
    await db.execute(
        update(ChatSession)
        .where(ChatSession.id == session_id)
        .values(name=request.name)
    )

    await db.commit()
    logger.info(f"[聊天API] 重命名会话: {session_id} -> {request.name}")

    # 查询消息数量
    count_result = await db.execute(
        select(func.count(ChatMessage.id)).where(ChatMessage.sessionId == session_id)
    )
    message_count = count_result.scalar() or 0

    # 重新获取会话信息
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    return ChatSessionResponse(
        id=session.id,
        hotspot_id=session.hotspotId,
        name=session.name,
        created_at=session.createdAt,
        updated_at=session.updatedAt,
        message_count=message_count,
    )
