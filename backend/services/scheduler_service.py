"""
定时调度服务模块
基于 APScheduler 实现定时采集+邮件推送（per-user）
"""
import uuid
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from backend.common.mysql import AsyncSessionLocal
from backend.common.logger import logger
from backend.models.scheduler import SchedulerConfig
from backend.api.v1.collection import run_collection_task
from backend.api.v1.fetch_quota import get_fetch_quotas
from backend.common.websocket import generate_task_id
from backend.services.email_service import EmailConfig


# 全局调度器实例
_scheduler: AsyncIOScheduler | None = None
# per-user 互斥锁：标记是否有采集任务正在运行
_is_collecting: dict[str, bool] = {}


async def _get_config(user_id: str) -> SchedulerConfig:
    """获取调度配置（per-user）"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SchedulerConfig).where(SchedulerConfig.userId == user_id)
        )
        config = result.scalar_one_or_none()
        if config is None:
            config = SchedulerConfig(
                id=str(uuid.uuid4()),
                userId=user_id,
                intervalHours=2,
                isEnabled=False,
            )
            session.add(config)
            await session.commit()
            await session.refresh(config)
        return config


async def _update_config_fields(user_id: str, **kwargs) -> SchedulerConfig:
    """更新调度配置字段并返回更新后的配置"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SchedulerConfig).where(SchedulerConfig.userId == user_id)
        )
        config = result.scalar_one()
        for key, value in kwargs.items():
            setattr(config, key, value)
        await session.commit()
        await session.refresh(config)
        return config


async def _scheduled_collect(user_id: str):
    """定时采集任务执行函数（per-user）"""
    if _is_collecting.get(user_id, False):
        logger.info(f"定时调度[{user_id[:8]}]: 上一轮采集仍在运行，跳过本次")
        await _update_config_fields(user_id,
            lastRunAt=datetime.now(),
            lastRunStatus="skipped",
        )
        return

    _is_collecting[user_id] = True
    task_id = generate_task_id()
    logger.info(f"定时调度[{user_id[:8]}]: 启动采集任务 {task_id}")

    try:
        # 获取该用户的激活关键词
        async with AsyncSessionLocal() as session:
            from backend.models import Keyword
            result = await session.execute(
                select(Keyword).where(Keyword.isActive == True, Keyword.userId == user_id)
            )
            keywords = result.scalars().all()

        if not keywords:
            logger.warning(f"定时调度[{user_id[:8]}]: 无激活关键词，跳过采集")
            await _update_config_fields(user_id,
                lastRunAt=datetime.now(),
                lastRunStatus="skipped",
            )
            _is_collecting[user_id] = False
            return

        keyword_ids = [k.id for k in keywords]

        # 创建独立数据库会话执行采集
        async_db = AsyncSessionLocal()

        # 判断是否配置了邮件（SMTP 全局配置 + 用户收件邮箱）
        from backend.services.settings_service import is_email_valid
        auto_email = EmailConfig.is_configured() and await is_email_valid(user_id)

        try:
            await run_collection_task(
                task_id=task_id,
                keyword_ids=keyword_ids,
                db_session=async_db,
                auto_email=auto_email,
                user_id=user_id,
            )
        finally:
            await async_db.close()

        await _update_config_fields(user_id,
            lastRunAt=datetime.now(),
            lastRunStatus="success",
        )
        logger.info(f"定时调度[{user_id[:8]}]: 采集任务 {task_id} 完成")

    except Exception as e:
        logger.error(f"定时调度[{user_id[:8]}]: 采集任务 {task_id} 失败 - {e}")
        await _update_config_fields(user_id,
            lastRunAt=datetime.now(),
            lastRunStatus="failed",
        )
    finally:
        _is_collecting[user_id] = False

    # 更新下次执行时间
    await _refresh_next_run_time(user_id)


async def _refresh_next_run_time(user_id: str):
    """刷新下次执行时间到数据库"""
    job_id = f"scheduled_collect_{user_id}"
    if _scheduler and _scheduler.running:
        job = _scheduler.get_job(job_id)
        if job and job.next_run_time:
            await _update_config_fields(user_id, nextRunAt=job.next_run_time.replace(tzinfo=None))
            return
    await _update_config_fields(user_id, nextRunAt=None)


def start_scheduler():
    """启动调度器（不添加任何 job，等待配置加载）"""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    if not _scheduler.running:
        _scheduler.start()
        logger.info("APScheduler 调度器已启动")


async def stop_scheduler():
    """停止调度器并清理 job"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.remove_all_jobs()
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler 调度器已停止")


async def _scheduled_douyin_cookie_renew(user_id: str):
    """定时检查抖音 Cookie 有效性并尝试续期（per-user）"""
    from backend.services.douyin_cookie_service import check_cookie_validity, try_auto_renew, is_douyin_cookie_active

    if not await is_douyin_cookie_active(user_id):
        return

    result = await check_cookie_validity(user_id)
    if result["valid"]:
        logger.info(f"抖音 Cookie 有效性检测[{user_id[:8]}]: 有效")
        return

    logger.warning(f"抖音 Cookie 有效性检测[{user_id[:8]}]: {result['message']}，尝试自动续期")
    renew_result = await try_auto_renew(user_id)

    if not renew_result["success"]:
        from backend.common.websocket import manager
        await manager.send_to_user(user_id, {
            "type": "douyin_cookie_expired",
            "status": "expired",
            "message": "抖音 Cookie 已过期且自动续期失败，请重新登录",
        })


async def load_scheduler_config():
    """从数据库加载所有用户的调度配置并应用"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SchedulerConfig).where(SchedulerConfig.isEnabled == True)
        )
        configs = result.scalars().all()

    for config in configs:
        await _apply_schedule(config.userId, config.intervalHours)
        logger.info(f"已加载用户 {config.userId[:8]} 的定时调度: 每 {config.intervalHours} 小时")

    # 注册所有用户的抖音 Cookie 自动续期检查（每 6 小时）
    _ensure_all_douyin_renew_jobs()
    logger.info("抖音 Cookie 自动续期检查已注册（每 6 小时）")


def _ensure_douyin_renew_job(user_id: str):
    """确保某用户的抖音 Cookie 续期任务已注册"""
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        return
    job_id = f"douyin_cookie_renew_{user_id}"
    _scheduler.add_job(
        _scheduled_douyin_cookie_renew,
        IntervalTrigger(hours=6),
        id=job_id,
        replace_existing=True,
        kwargs={"user_id": user_id},
    )


def _ensure_all_douyin_renew_jobs():
    """为所有有抖音 Cookie 的用户注册续期任务"""
    import asyncio
    async def _register():
        from backend.models.douyin_cookie import DouyinCookie
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DouyinCookie.userId).distinct()
            )
            user_ids = [row[0] for row in result.fetchall()]
        for uid in user_ids:
            _ensure_douyin_renew_job(uid)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_register())
        else:
            loop.run_until_complete(_register())
    except RuntimeError:
        asyncio.ensure_future(_register())


async def _apply_schedule(user_id: str, interval_hours: int):
    """应用调度配置：添加该用户的 job"""
    global _scheduler
    if _scheduler is None:
        return

    job_id = f"scheduled_collect_{user_id}"
    _scheduler.add_job(
        _scheduled_collect,
        IntervalTrigger(hours=interval_hours),
        id=job_id,
        replace_existing=True,
        kwargs={"user_id": user_id},
    )
    logger.info(f"用户 {user_id[:8]} 定时调度已配置：每 {interval_hours} 小时执行一次")

    # 刷新下次执行时间
    await _refresh_next_run_time(user_id)


async def update_schedule(user_id: str, is_enabled: bool, interval_hours: int):
    """更新调度配置（开关+间隔）"""
    config = await _update_config_fields(user_id,
        isEnabled=is_enabled,
        intervalHours=interval_hours,
    )

    collect_job_id = f"scheduled_collect_{user_id}"
    if is_enabled:
        await _apply_schedule(user_id, interval_hours)
    else:
        if _scheduler:
            _scheduler.remove_job(collect_job_id)
        await _update_config_fields(user_id, nextRunAt=None)
        logger.info(f"用户 {user_id[:8]} 定时调度已关闭")

    return config


async def get_scheduler_status(user_id: str) -> dict:
    """获取调度运行状态"""
    config = await _get_config(user_id)
    return {
        "isEnabled": config.isEnabled,
        "intervalHours": config.intervalHours,
        "lastRunAt": config.lastRunAt.isoformat() if config.lastRunAt else None,
        "lastRunStatus": config.lastRunStatus,
        "nextRunAt": config.nextRunAt.isoformat() if config.nextRunAt else None,
        "isCollecting": _is_collecting.get(user_id, False),
    }
