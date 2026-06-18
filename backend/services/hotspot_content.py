"""
热点完整内容获取服务

负责获取热点的完整原文内容，包括视频音频的实时转录
"""
import asyncio
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.models.hotspot import Hotspot
from backend.services.video_transcribe import fetch_video_content
from backend.common.logger import logger

# 视频转录整体超时（秒），包含字幕提取 + 音频下载 + ASR
VIDEO_TRANSCRIBE_TIMEOUT = 100


async def get_full_content(hotspot: Hotspot, db: AsyncSession) -> str:
    """
    获取热点的完整内容

    优先级：
    1. 如果 fullContent 字段已有值，直接返回
    2. 如果是视频类热点，尝试转录音频（有超时限制）
    3. 其他情况返回 content 字段

    Args:
        hotspot: 热点对象
        db: 数据库会话

    Returns:
        完整内容文本
    """
    # 1. 如果已有完整内容，直接返回
    if hotspot.fullContent:
        return hotspot.fullContent

    # 2. 视频类热点需要转录音频
    if hotspot.source in ["bilibili", "youtube", "douyin"] and hotspot.url:
        logger.info(f"[内容获取] 视频热点尝试转录: {hotspot.id}")

        try:
            text = await asyncio.wait_for(
                fetch_video_content(hotspot.url, hotspot.content or ""),
                timeout=VIDEO_TRANSCRIBE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning(f"[内容获取] 视频转录超时({VIDEO_TRANSCRIBE_TIMEOUT}s)，使用描述: {hotspot.id}")
            text = None

        if text and text != (hotspot.content or ""):
            # 转录成功，存入数据库
            await update_full_content(db, hotspot.id, text)
            return text
        else:
            # 转录失败或超时，将视频描述存入 fullContent（避免下次重复尝试）
            logger.info(f"[内容获取] 使用描述作为内容: {hotspot.id}")
            if hotspot.content:
                await update_full_content(db, hotspot.id, hotspot.content)
            return hotspot.content or ""

    # 3. 其他数据源使用现有 content
    return hotspot.content or ""


async def update_full_content(db: AsyncSession, hotspot_id: str, content: str) -> None:
    """
    更新热点的 fullContent 字段

    Args:
        db: 数据库会话
        hotspot_id: 热点ID
        content: 内容文本
    """
    try:
        stmt = update(Hotspot).where(Hotspot.id == hotspot_id).values(fullContent=content)
        await db.execute(stmt)
        await db.commit()
        logger.info(f"[内容获取] 已缓存完整内容: {hotspot_id}")
    except Exception as e:
        logger.warning(f"[内容获取] 缓存内容失败: {e}")
        await db.rollback()


async def get_hotspot_with_content(db: AsyncSession, hotspot_id: str) -> Optional[Hotspot]:
    """
    获取热点并确保有完整内容

    Args:
        db: 数据库会话
        hotspot_id: 热点ID

    Returns:
        热点对象，不存在返回None
    """
    result = await db.execute(select(Hotspot).where(Hotspot.id == hotspot_id))
    hotspot = result.scalar_one_or_none()

    if not hotspot:
        return None

    # 确保获取完整内容
    if not hotspot.fullContent:
        await get_full_content(hotspot, db)
        # 重新获取更新后的热点
        result = await db.execute(select(Hotspot).where(Hotspot.id == hotspot_id))
        hotspot = result.scalar_one_or_none()

    return hotspot


async def get_hotspot_by_id(db: AsyncSession, hotspot_id: str) -> Optional[Hotspot]:
    """
    获取热点（简单查询，不获取完整内容）

    Args:
        db: 数据库会话
        hotspot_id: 热点ID

    Returns:
        热点对象，不存在返回None
    """
    result = await db.execute(select(Hotspot).where(Hotspot.id == hotspot_id))
    return result.scalar_one_or_none()