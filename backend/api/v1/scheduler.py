"""
定时调度接口
GET /scheduler/config - 获取调度配置
PUT /scheduler/config - 更新调度配置
GET /scheduler/status - 获取调度运行状态
"""
from fastapi import APIRouter, Depends, HTTPException
from backend.common.auth import get_current_user
from backend.schemas.request.scheduler import SchedulerConfigRequest
from backend.schemas.response.scheduler import SchedulerConfigResponse, SchedulerStatusResponse
from backend.services.scheduler_service import update_schedule, get_scheduler_status
from backend.services.settings_service import is_llm_ready
from backend.common.logger import logger

router = APIRouter()


@router.get(
    "/config",
    response_model=SchedulerConfigResponse,
    summary="获取调度配置",
)
async def get_scheduler_config(current_user: str = Depends(get_current_user)):
    """获取当前定时调度配置"""
    status = await get_scheduler_status(current_user)
    return SchedulerConfigResponse(
        isEnabled=status["isEnabled"],
        intervalHours=status["intervalHours"],
    )


@router.put(
    "/config",
    response_model=SchedulerConfigResponse,
    summary="更新调度配置",
    description="更新定时调度的开关状态和间隔时间，配置会持久化到数据库",
)
async def put_scheduler_config(request: SchedulerConfigRequest, current_user: str = Depends(get_current_user)):
    """更新定时调度配置"""
    # 开启定时推送需要 LLM 已配置
    if request.isEnabled and not await is_llm_ready(current_user):
        raise HTTPException(status_code=503, detail="请先在设置中配置并测试 LLM")

    config = await update_schedule(
        is_enabled=request.isEnabled,
        interval_hours=request.intervalHours,
        user_id=current_user,
    )
    return SchedulerConfigResponse(
        isEnabled=config.isEnabled,
        intervalHours=config.intervalHours,
    )


@router.get(
    "/status",
    response_model=SchedulerStatusResponse,
    summary="获取调度运行状态",
)
async def get_scheduler_status_api(current_user: str = Depends(get_current_user)):
    """获取调度运行状态，包含上次执行结果和下次执行时间"""
    status = await get_scheduler_status(current_user)
    return SchedulerStatusResponse(**status)
