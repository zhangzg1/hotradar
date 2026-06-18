"""
采集任务接口
POST /collections - 创建采集任务（无自动邮件）
POST /collections/auto-email - 创建采集任务（含自动邮件）
"""
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from backend.common.mysql import get_async_db
from backend.common.auth import get_current_user
from backend.models import Keyword, Hotspot
from backend.schemas.request import CollectionRequest
from backend.schemas.response import CollectionResponse, ErrorResponse
from backend.common.websocket import generate_task_id, manager, build_hotspot_message
from backend.services.email_service import send_hotspot_email, EmailConfig
from backend.common.logger import logger
from backend.common.redis_client import get_redis
from backend.api.v1.fetch_quota import get_fetch_quotas
from backend.services.settings_service import is_llm_ready, is_email_valid
from agents.hotspot_collect_agent.graph import run_workflow


router = APIRouter()


async def run_collection_task(
    task_id: str,
    keyword_ids: list,
    db_session: AsyncSession,
    auto_email: bool = False,
    user_id: str = None,
):
    """
    执行采集任务的异步函数

    Args:
        task_id: 任务ID
        keyword_ids: 关键词ID列表
        db_session: 数据库会话
        auto_email: 是否自动发送邮件
        user_id: 用户ID
    """
    try:
        # 等待前端 WebSocket 连接建立，避免消息在连接完成前发送被丢弃
        import asyncio
        await asyncio.sleep(0.5)

        redis = get_redis()
        progress_key = f"task_progress:{task_id}"

        # 发送开始状态
        await redis.hset(progress_key, {
            "status": "running",
            "total_keywords": str(len(keyword_ids)),
            "current_idx": "0",
            "hotspots_found": "0",
        })
        await redis.set(progress_key + ":ttl", "1", ex=3600)
        # 给 hash 也设置 TTL（通过 expire）
        if redis.available:
            try:
                await redis._client.expire(progress_key, 3600)
            except Exception:
                pass

        await manager.send_to_task(task_id, user_id, {
            "type": "collection_status",
            "data": {
                "taskId": task_id,
                "status": "started",
                "totalKeywords": len(keyword_ids),
            }
        })

        # 获取关键词信息
        result = await db_session.execute(
            select(Keyword).where(Keyword.id.in_(keyword_ids))
        )
        keywords = result.scalars().all()

        if not keywords:
            logger.warning(f"任务 {task_id}: 无有效关键词")
            await manager.send_to_task(task_id, user_id, {
                "type": "collection_status",
                "data": {
                    "taskId": task_id,
                    "status": "completed",
                    "keyword": "",
                }
            })
            return

        # 获取用户配置的抓取配额
        fetch_quotas = await get_fetch_quotas(user_id=user_id)

        # 补偿检查：如果抖音开关开着但 Cookie 已过期，自动关闭
        if fetch_quotas.get("douyinEnabled"):
            from backend.services.douyin_cookie_service import is_douyin_cookie_active
            if not await is_douyin_cookie_active(user_id):
                fetch_quotas["douyinEnabled"] = False
                logger.warning("抖音 Cookie 已过期，本次采集自动跳过抖音数据源")

        # 衍生启用的数据源列表
        all_sources = ["twitter", "youtube", "bilibili", "douyin", "bing", "sogou"]
        enabled_sources = [s for s in all_sources if fetch_quotas.get(f"{s}Enabled", True)]

        # 逐个关键词执行工作流，每完成一个立即推送进度
        workflow_results = []
        total_found = 0

        for idx, kw in enumerate(keywords, 1):
            workflow_result = await run_workflow(
                kw.text, kw.id,
                fetch_quotas=fetch_quotas,
                enabled_sources=enabled_sources,
                user_id=user_id,
            )
            workflow_results.append(workflow_result)

            saved_hotspots = workflow_result.get("savedHotspots", [])
            total_found += len(saved_hotspots)

            # 更新 Redis 进度
            await redis.hset(progress_key, {
                "current_idx": str(idx),
                "hotspots_found": str(total_found),
            })

            # 推送热点数据
            if saved_hotspots:
                message = build_hotspot_message(
                    task_id=task_id,
                    keyword_id=kw.id,
                    keyword=kw.text,
                    hotspots=saved_hotspots,
                    auto_email_triggered=auto_email,
                )
                await manager.send_to_task(task_id, user_id, message)

            # 推送关键词完成状态
            await manager.send_to_task(task_id, user_id, {
                "type": "collection_status",
                "data": {
                    "taskId": task_id,
                    "status": "keyword_completed",
                    "keyword": kw.text,
                    "hotspotsCount": len(saved_hotspots),
                }
            })

        # 自动邮件通知
        if auto_email and EmailConfig.is_configured():
            # 筛选本次采集的高重要性热点
            hotspot_ids = []
            for workflow_result in workflow_results:
                for hotspot in workflow_result.get("savedHotspots", []):
                    if hotspot.get("importance") in ["high", "urgent"]:
                        hotspot_ids.append(hotspot.get("id"))

            logger.info(f"任务 {task_id}: 高重要性热点 ID 列表: {hotspot_ids}")

            if hotspot_ids:
                result = await db_session.execute(
                    select(Hotspot).where(Hotspot.id.in_(hotspot_ids))
                )
                hotspots = result.scalars().all()
                logger.info(f"任务 {task_id}: 查询到 {len(hotspots)} 条高重要性热点")

                if hotspots:
                    await send_hotspot_email(db_session, list(hotspots), user_id=user_id)
                    logger.info(f"任务 {task_id}: 自动邮件发送完成")
                else:
                    logger.warning(f"任务 {task_id}: 未查询到热点，尝试刷新后重新查询")
                    # 刷新 session 状态并重新查询
                    await db_session.commit()
                    result = await db_session.execute(
                        select(Hotspot).where(Hotspot.id.in_(hotspot_ids))
                    )
                    hotspots = result.scalars().all()
                    logger.info(f"任务 {task_id}: 刷新后查询到 {len(hotspots)} 条热点")
                    if hotspots:
                        await send_hotspot_email(db_session, list(hotspots), user_id=user_id)

        # 发送全部完成状态
        total_hotspots = sum(len(w.get("savedHotspots", [])) for w in workflow_results)
        await redis.hset(progress_key, {
            "status": "completed",
            "current_idx": str(len(workflow_results)),
            "hotspots_found": str(total_hotspots),
        })
        await manager.send_to_task(task_id, user_id, {
            "type": "collection_status",
            "data": {
                "taskId": task_id,
                "status": "completed",
                "keyword": f"全部 {len(keywords)} 个关键词",
                "totalHotspots": total_hotspots,
            }
        })

        logger.info(f"任务 {task_id}: 采集完成")

    except Exception as e:
        logger.error(f"任务 {task_id}: 执行失败 - {e}")
        redis = get_redis()
        await redis.hset(f"task_progress:{task_id}", {"status": "failed", "error": str(e)})
        await manager.send_to_task(task_id, user_id, {
            "type": "collection_error",
            "data": {
                "taskId": task_id,
                "error": str(e),
            }
        })

    finally:
        await db_session.close()


@router.post(
    "",
    response_model=CollectionResponse,
    responses={400: {"model": ErrorResponse}},
    summary="创建采集任务",
    description="触发热点采集，执行工作流抓取热点数据并通过 WebSocket 推送结果（不发送邮件）",
)
async def create_collection(
    request: CollectionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """
    创建采集任务（无自动邮件）

    - 执行工作流采集热点
    - WebSocket 推送采集结果
    - 不发送邮件通知
    """
    if not request.keywordIds:
        raise HTTPException(status_code=400, detail="请提供关键词ID列表")

    if not await is_llm_ready(current_user):
        raise HTTPException(status_code=503, detail="请先在设置中配置并测试 LLM")

    task_id = generate_task_id()

    from backend.common.mysql import AsyncSessionLocal
    async_db = AsyncSessionLocal()

    background_tasks.add_task(
        run_collection_task,
        task_id,
        request.keywordIds,
        async_db,
        False,
        current_user,
    )

    logger.info(f"采集任务已启动: {task_id}")

    return CollectionResponse(
        taskId=task_id,
        status="running",
        message="采集任务已启动",
    )


@router.post(
    "/auto-email",
    response_model=CollectionResponse,
    responses={400: {"model": ErrorResponse}},
    summary="创建采集任务（含自动邮件）",
    description="触发热点采集，执行工作流抓取热点数据并通过 WebSocket 推送结果，同时自动发送邮件通知",
)
async def create_collection_with_auto_email(
    request: CollectionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """
    创建采集任务（含自动邮件）

    - 执行工作流采集热点
    - WebSocket 推送采集结果
    - 自动发送邮件（仅高重要性热点）
    """
    if not request.keywordIds:
        raise HTTPException(status_code=400, detail="请提供关键词ID列表")

    if not await is_llm_ready(current_user):
        raise HTTPException(status_code=503, detail="请先在设置中配置并测试 LLM")

    if not EmailConfig.is_configured():
        raise HTTPException(status_code=503, detail="邮件配置不完整，请检查 .env 中的 SMTP 配置")

    if not await is_email_valid(current_user):
        raise HTTPException(status_code=503, detail="请先在设置中配置有效的收件邮箱")

    task_id = generate_task_id()

    from backend.common.mysql import AsyncSessionLocal
    async_db = AsyncSessionLocal()

    background_tasks.add_task(
        run_collection_task,
        task_id,
        request.keywordIds,
        async_db,
        True,
        current_user,
    )

    logger.info(f"采集任务（含自动邮件）已启动: {task_id}")

    return CollectionResponse(
        taskId=task_id,
        status="running",
        message="采集任务已启动，将自动发送邮件通知",
    )
