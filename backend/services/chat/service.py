"""
热点问答聊天服务

核心业务逻辑：处理用户消息，调用LLM，处理Tool Calling
支持流式输出
"""
import json
import uuid
from typing import Optional, List, Tuple, AsyncGenerator
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool

from backend.models.hotspot import Hotspot
from backend.models.chat import ChatSession, ChatMessage
from backend.models.keyword import Keyword
from backend.services.hotspot_content import get_full_content, get_hotspot_with_content, get_hotspot_by_id
from backend.services.chat.prompts import build_system_prompt
from backend.common.logger import logger
from llm.fallback_llm import invoke_with_tools_fallback_async, stream_with_user_llm


# ==================== Tool 定义 ====================
@tool
def load_hotspot_detail(hotspot_id: str) -> str:
    """
    加载指定热点的完整原文内容

    Args:
        hotspot_id: 热点ID

    Returns:
        热点的完整内容文本
    """
    # 这是一个占位符，实际执行在 process_chat 中动态处理
    return f"[待加载热点: {hotspot_id}]"


# Tool schema for LLM
LOAD_HOTSPOT_TOOL = {
    "type": "function",
    "function": {
        "name": "load_hotspot_detail",
        "description": "加载指定热点的完整原文内容。当用户问题需要其他热点的详细信息时，调用此工具获取完整内容。",
        "parameters": {
            "type": "object",
            "properties": {
                "hotspot_id": {
                    "type": "string",
                    "description": "热点ID，可以从同关键词热点概览中获取"
                }
            },
            "required": ["hotspot_id"]
        }
    }
}


# ==================== 会话管理 ====================
async def get_or_create_session(
    db: AsyncSession,
    hotspot_id: str,
    session_id: Optional[str] = None,
) -> Tuple[ChatSession, List[ChatMessage]]:
    """
    获取或创建聊天会话

    Args:
        db: 数据库会话
        hotspot_id: 热点ID
        session_id: 会话ID（可选）

    Returns:
        (会话对象, 历史消息列表)
    """
    if session_id:
        # 获取现有会话
        result = await db.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        session = result.scalar_one_or_none()

        if session and session.hotspotId == hotspot_id:
            # 获取历史消息
            msg_result = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.sessionId == session_id)
                .order_by(ChatMessage.createdAt)
            )
            messages = msg_result.scalars().all()
            return session, list(messages)

    # 创建新会话
    new_session = ChatSession(
        id=str(uuid.uuid4()),
        hotspotId=hotspot_id,
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)

    return new_session, []


async def save_messages(
    db: AsyncSession,
    session_id: str,
    user_message: str,
    assistant_reply: str,
    loaded_hotspots: Optional[List[str]] = None,
) -> None:
    """
    保存聊天消息

    Args:
        db: 数据库会话
        session_id: 会话ID
        user_message: 用户消息
        assistant_reply: AI回复
        loaded_hotspots: 加载的其他热点ID列表
    """
    # 保存用户消息
    user_msg = ChatMessage(
        id=str(uuid.uuid4()),
        sessionId=session_id,
        role="user",
        content=user_message,
    )
    db.add(user_msg)

    # 保存AI回复
    assistant_msg = ChatMessage(
        id=str(uuid.uuid4()),
        sessionId=session_id,
        role="assistant",
        content=assistant_reply,
        loadedHotspots=json.dumps(loaded_hotspots) if loaded_hotspots else None,
    )
    db.add(assistant_msg)

    # 更新会话时间
    await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    # SQLAlchemy会自动更新updatedAt

    await db.commit()


# ==================== 热点信息获取 ====================
async def get_same_keyword_hotspots(
    db: AsyncSession,
    keyword_id: Optional[str],
    exclude_id: str,
) -> List[dict]:
    """
    获取同关键词的其他热点概览

    Args:
        db: 数据库会话
        keyword_id: 关键词ID
        exclude_id: 排除的热点ID

    Returns:
        热点概览列表（仅标题、摘要、ID、来源）
    """
    if not keyword_id:
        return []

    result = await db.execute(
        select(Hotspot)
        .where(Hotspot.keywordId == keyword_id)
        .where(Hotspot.id != exclude_id)
        .order_by(desc(Hotspot.relevance))
        .limit(50)  # 获取所有同关键词热点
    )
    hotspots = result.scalars().all()

    return [
        {
            "id": h.id,
            "title": h.title,
            "summary": h.summary,
            "source": h.source,
            "relevance": h.relevance,
        }
        for h in hotspots
    ]


# ==================== 聊天处理 ====================
async def process_chat(
    db: AsyncSession,
    hotspot_id: str,
    message: str,
    session_id: Optional[str] = None,
    user_id: str = None,
) -> Tuple[str, str, Optional[List[str]]]:
    """
    处理聊天消息

    Args:
        db: 数据库会话
        hotspot_id: 热点ID
        message: 用户消息
        session_id: 会话ID（可选）

    Returns:
        (AI回复, 会话ID, 加载的其他热点ID列表)
    """
    logger.info(f"[聊天] 处理消息: hotspot={hotspot_id}, session={session_id}")

    # 1. 获取热点完整内容
    hotspot = await get_hotspot_with_content(db, hotspot_id)
    if not hotspot:
        raise ValueError(f"热点不存在: {hotspot_id}")

    full_content = hotspot.fullContent or hotspot.content or ""

    # 2. 获取关键词文本
    keyword_text = ""
    if hotspot.keywordId:
        kw_result = await db.execute(select(Keyword).where(Keyword.id == hotspot.keywordId))
        keyword_obj = kw_result.scalar_one_or_none()
        if keyword_obj:
            keyword_text = keyword_obj.text

    # 3. 获取同关键词其他热点
    other_hotspots = await get_same_keyword_hotspots(db, hotspot.keywordId, hotspot_id)

    # 4. 构建系统提示词
    hotspot_info = {
        "title": hotspot.title,
        "source": hotspot.source,
        "summary": hotspot.summary or "无",
    }
    system_prompt = build_system_prompt(hotspot_info, full_content, other_hotspots, keyword_text)

    # 5. 获取/创建会话，加载历史消息
    session, history_messages = await get_or_create_session(db, hotspot_id, session_id)

    # 6. 构建消息列表
    messages = [SystemMessage(content=system_prompt)]

    # 添加历史消息
    for msg in history_messages:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))

    # 添加当前用户消息
    messages.append(HumanMessage(content=message))

    # 7. 调用LLM（带Tool Calling）- 使用轮询机制
    loaded_hotspots: List[str] = []
    final_reply = ""

    try:
        # 第一轮调用 - 使用轮询机制
        response = await invoke_with_tools_fallback_async(messages, [LOAD_HOTSPOT_TOOL], user_id=user_id)

        # 处理Tool Calling循环
        while response.tool_calls:
            logger.info(f"[聊天] Tool Calling: {len(response.tool_calls)} 个调用")

            # 将AI响应添加到消息列表
            messages.append(response)

            # 处理每个tool call
            for tool_call in response.tool_calls:
                if tool_call["name"] == "load_hotspot_detail":
                    other_hotspot_id = tool_call["args"]["hotspot_id"]
                    loaded_hotspots.append(other_hotspot_id)

                    # 获取其他热点完整内容
                    other_hotspot = await get_hotspot_with_content(db, other_hotspot_id)
                    if other_hotspot:
                        other_content = other_hotspot.fullContent or other_hotspot.content or ""
                        tool_result = f"热点标题: {other_hotspot.title}\n来源: {other_hotspot.source}\n完整内容:\n{other_content[:2000]}"
                    else:
                        tool_result = f"热点 {other_hotspot_id} 不存在或无法获取"

                    messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call["id"]))

            # 继续调用LLM - 使用轮询机制
            response = await invoke_with_tools_fallback_async(messages, [LOAD_HOTSPOT_TOOL], user_id=user_id)

        # 最终响应
        final_reply = response.content or ""

    except Exception as e:
        logger.error(f"[聊天] LLM调用失败: {e}")
        final_reply = f"抱歉，处理您的消息时出现错误: {str(e)}"

    # 8. 保存消息
    await save_messages(db, session.id, message, final_reply, loaded_hotspots)

    logger.info(f"[聊天] 完成: session={session.id}, loaded={loaded_hotspots}")

    return final_reply, session.id, loaded_hotspots if loaded_hotspots else None


# ==================== 流式聊天处理 ====================
async def process_chat_stream(
    db: AsyncSession,
    hotspot_id: str,
    message: str,
    session_id: Optional[str] = None,
    user_id: str = None,
) -> AsyncGenerator[str, None]:
    """
    流式处理聊天消息

    先处理 Tool Calling，再流式输出最终回复

    Args:
        db: 数据库会话
        hotspot_id: 热点ID
        message: 用户消息
        session_id: 会话ID（可选）

    Yields:
        SSE 格式的数据片段
    """
    logger.info(f"[聊天-流式] 处理消息: hotspot={hotspot_id}, session={session_id}")

    # 1. 获取热点完整内容
    hotspot = await get_hotspot_with_content(db, hotspot_id)
    if not hotspot:
        yield f"data: {json.dumps({'error': '热点不存在'})}\n\n"
        return

    full_content = hotspot.fullContent or hotspot.content or ""

    # 2. 获取关键词文本
    keyword_text = ""
    if hotspot.keywordId:
        kw_result = await db.execute(select(Keyword).where(Keyword.id == hotspot.keywordId))
        keyword_obj = kw_result.scalar_one_or_none()
        if keyword_obj:
            keyword_text = keyword_obj.text

    # 3. 获取同关键词其他热点
    other_hotspots = await get_same_keyword_hotspots(db, hotspot.keywordId, hotspot_id)

    # 4. 构建系统提示词
    hotspot_info = {
        "title": hotspot.title,
        "source": hotspot.source,
        "summary": hotspot.summary or "无",
    }
    system_prompt = build_system_prompt(hotspot_info, full_content, other_hotspots, keyword_text)

    # 5. 获取/创建会话，加载历史消息
    session, history_messages = await get_or_create_session(db, hotspot_id, session_id)

    # 发送会话ID
    yield f"data: {json.dumps({'type': 'session', 'session_id': session.id})}\n\n"

    # 6. 构建消息列表
    messages = [SystemMessage(content=system_prompt)]

    # 添加历史消息
    for msg in history_messages:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))

    # 添加当前用户消息
    messages.append(HumanMessage(content=message))

    # 7. 先处理 Tool Calling（非流式）
    loaded_hotspots: List[str] = []

    try:
        # 使用轮询机制处理 Tool Calling
        response = await invoke_with_tools_fallback_async(messages, [LOAD_HOTSPOT_TOOL], user_id=user_id)

        # 处理Tool Calling循环
        while response.tool_calls:
            logger.info(f"[聊天-流式] Tool Calling: {len(response.tool_calls)} 个调用")

            # 发送 tool calling 状态
            yield f"data: {json.dumps({'type': 'tool_call', 'count': len(response.tool_calls)})}\n\n"

            # 将AI响应添加到消息列表
            messages.append(response)

            # 处理每个tool call
            for tool_call in response.tool_calls:
                if tool_call["name"] == "load_hotspot_detail":
                    other_hotspot_id = tool_call["args"]["hotspot_id"]
                    loaded_hotspots.append(other_hotspot_id)

                    # 发送加载热点状态
                    yield f"data: {json.dumps({'type': 'loading_hotspot', 'hotspot_id': other_hotspot_id})}\n\n"

                    # 获取其他热点完整内容
                    other_hotspot = await get_hotspot_with_content(db, other_hotspot_id)
                    if other_hotspot:
                        other_content = other_hotspot.fullContent or other_hotspot.content or ""
                        tool_result = f"热点标题: {other_hotspot.title}\n来源: {other_hotspot.source}\n完整内容:\n{other_content[:2000]}"
                    else:
                        tool_result = f"热点 {other_hotspot_id} 不存在或无法获取"

                    messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call["id"]))

            # 继续调用LLM
            response = await invoke_with_tools_fallback_async(messages, [LOAD_HOTSPOT_TOOL], user_id=user_id)

        # 8. 流式输出最终回复
        final_reply = ""

        try:
            logger.info(f"[聊天-流式] 使用用户配置 LLM 流式输出")

            async for chunk in stream_with_user_llm(messages, user_id=user_id):
                final_reply += chunk
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

            logger.info(f"[聊天-流式] 流式输出完成")

        except Exception as e:
            logger.warning(f"[聊天-流式] 流式输出失败: {e}")
            raise

        # 发送结束信号
        yield f"data: {json.dumps({'type': 'done', 'loaded_hotspots': loaded_hotspots})}\n\n"

        # 9. 保存消息
        await save_messages(db, session.id, message, final_reply, loaded_hotspots)

        logger.info(f"[聊天-流式] 完成: session={session.id}, loaded={loaded_hotspots}")

    except Exception as e:
        logger.error(f"[聊天-流式] 处理失败: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"