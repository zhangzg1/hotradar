"""
数据源抓取配额接口
GET /fetch-quotas - 获取抓取配额配置
PUT /fetch-quotas - 更新抓取配额配置
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from backend.common.mysql import AsyncSessionLocal
from backend.common.auth import get_current_user
from backend.models.fetch_quota import FetchQuotaConfig
from backend.schemas.request.fetch_quota import FetchQuotaRequest
from backend.schemas.response.fetch_quota import FetchQuotaResponse
from backend.common.logger import logger

router = APIRouter()

DEFAULT_QUOTAS = {
    "twitter": 8,
    "youtube": 8,
    "bilibili": 3,
    "douyin": 3,
    "bing": 2,
    "sogou": 1,
    "twitterEnabled": True,
    "youtubeEnabled": True,
    "bilibiliEnabled": True,
    "douyinEnabled": True,
    "bingEnabled": True,
    "sogouEnabled": True,
}


async def _get_or_create_config(user_id: str) -> FetchQuotaConfig:
    """获取或创建配额配置（按用户隔离）"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(FetchQuotaConfig).where(FetchQuotaConfig.userId == user_id).limit(1)
        )
        config = result.scalar_one_or_none()
        if config is None:
            config = FetchQuotaConfig(
                id=str(uuid.uuid4()),
                userId=user_id,
                **DEFAULT_QUOTAS,
            )
            session.add(config)
            await session.commit()
            await session.refresh(config)
        return config


async def get_fetch_quotas(user_id: str = None) -> dict:
    """获取当前抓取配额（供其他模块调用）"""
    config = await _get_or_create_config(user_id)
    return {
        "twitter": config.twitter,
        "youtube": config.youtube,
        "bilibili": config.bilibili,
        "douyin": config.douyin,
        "bing": config.bing,
        "sogou": config.sogou,
        "twitterEnabled": config.twitterEnabled,
        "youtubeEnabled": config.youtubeEnabled,
        "bilibiliEnabled": config.bilibiliEnabled,
        "douyinEnabled": config.douyinEnabled,
        "bingEnabled": config.bingEnabled,
        "sogouEnabled": config.sogouEnabled,
    }


@router.get(
    "",
    response_model=FetchQuotaResponse,
    summary="获取抓取配额",
)
async def get_fetch_quota_config(current_user: str = Depends(get_current_user)):
    """获取当前各数据源的抓取配额设置"""
    config = await _get_or_create_config(current_user)
    from backend.services.douyin_cookie_service import is_douyin_cookie_active
    douyin_cookie_active = await is_douyin_cookie_active(current_user)
    return FetchQuotaResponse(
        twitter=config.twitter,
        youtube=config.youtube,
        bilibili=config.bilibili,
        douyin=config.douyin,
        bing=config.bing,
        sogou=config.sogou,
        twitterEnabled=config.twitterEnabled,
        youtubeEnabled=config.youtubeEnabled,
        bilibiliEnabled=config.bilibiliEnabled,
        douyinEnabled=config.douyinEnabled,
        bingEnabled=config.bingEnabled,
        sogouEnabled=config.sogouEnabled,
        douyinCookieActive=douyin_cookie_active,
    )


@router.put(
    "",
    response_model=FetchQuotaResponse,
    summary="更新抓取配额",
    description="更新各数据源的抓取配额，配置会持久化到数据库",
)
async def put_fetch_quota_config(request: FetchQuotaRequest, current_user: str = Depends(get_current_user)):
    """更新抓取配额配置"""
    # 校验：启用抖音需要先配置 Cookie
    if request.douyinEnabled:
        from backend.services.douyin_cookie_service import is_douyin_cookie_active
        if not await is_douyin_cookie_active(current_user):
            raise HTTPException(
                status_code=400,
                detail="启用抖音数据源前，请先登录抖音获取 Cookie",
            )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(FetchQuotaConfig).where(FetchQuotaConfig.userId == current_user).limit(1)
        )
        config = result.scalar_one_or_none()
        if config is None:
            config = FetchQuotaConfig(
                id=str(uuid.uuid4()),
                userId=current_user,
                twitter=request.twitter,
                youtube=request.youtube,
                bilibili=request.bilibili,
                douyin=request.douyin,
                bing=request.bing,
                sogou=request.sogou,
                twitterEnabled=request.twitterEnabled,
                youtubeEnabled=request.youtubeEnabled,
                bilibiliEnabled=request.bilibiliEnabled,
                douyinEnabled=request.douyinEnabled,
                bingEnabled=request.bingEnabled,
                sogouEnabled=request.sogouEnabled,
            )
            session.add(config)
        else:
            config.twitter = request.twitter
            config.youtube = request.youtube
            config.bilibili = request.bilibili
            config.douyin = request.douyin
            config.bing = request.bing
            config.sogou = request.sogou
            config.twitterEnabled = request.twitterEnabled
            config.youtubeEnabled = request.youtubeEnabled
            config.bilibiliEnabled = request.bilibiliEnabled
            config.douyinEnabled = request.douyinEnabled
            config.bingEnabled = request.bingEnabled
            config.sogouEnabled = request.sogouEnabled
        await session.commit()
        await session.refresh(config)

    logger.info(f"抓取配额已更新: twitter={config.twitter}/{config.twitterEnabled}, youtube={config.youtube}/{config.youtubeEnabled}, bilibili=config.bilibili/{config.bilibiliEnabled}, douyin={config.douyin}/{config.douyinEnabled}, bing={config.bing}/{config.bingEnabled}, sogou={config.sogou}/{config.sogouEnabled}")

    from backend.services.douyin_cookie_service import is_douyin_cookie_active
    douyin_cookie_active = await is_douyin_cookie_active(current_user)

    return FetchQuotaResponse(
        twitter=config.twitter,
        youtube=config.youtube,
        bilibili=config.bilibili,
        douyin=config.douyin,
        bing=config.bing,
        sogou=config.sogou,
        twitterEnabled=config.twitterEnabled,
        youtubeEnabled=config.youtubeEnabled,
        bilibiliEnabled=config.bilibiliEnabled,
        douyinEnabled=config.douyinEnabled,
        bingEnabled=config.bingEnabled,
        sogouEnabled=config.sogouEnabled,
        douyinCookieActive=douyin_cookie_active,
    )
