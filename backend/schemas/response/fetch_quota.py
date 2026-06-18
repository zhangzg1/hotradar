"""数据源抓取配额响应体"""
from pydantic import BaseModel, Field


class FetchQuotaResponse(BaseModel):
    """抓取配额响应"""
    twitter: int = Field(..., description="Twitter 配额")
    youtube: int = Field(..., description="YouTube 配额")
    bilibili: int = Field(..., description="Bilibili 配额")
    douyin: int = Field(..., description="抖音 配额")
    bing: int = Field(..., description="Bing 配额")
    sogou: int = Field(..., description="搜狗 配额")
    twitterEnabled: bool = Field(..., description="Twitter 是否启用")
    youtubeEnabled: bool = Field(..., description="YouTube 是否启用")
    bilibiliEnabled: bool = Field(..., description="Bilibili 是否启用")
    douyinEnabled: bool = Field(..., description="抖音 是否启用")
    bingEnabled: bool = Field(..., description="Bing 是否启用")
    sogouEnabled: bool = Field(..., description="搜狗 是否启用")
    douyinCookieActive: bool = Field(False, description="抖音 Cookie 是否有效（前端用于控制开关状态）")
