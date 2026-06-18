"""数据源抓取配额请求体"""
from pydantic import BaseModel, Field


class FetchQuotaRequest(BaseModel):
    """抓取配额更新请求"""
    twitter: int = Field(8, ge=1, le=20, description="Twitter 配额")
    youtube: int = Field(8, ge=1, le=20, description="YouTube 配额")
    bilibili: int = Field(3, ge=1, le=20, description="Bilibili 配额")
    douyin: int = Field(3, ge=1, le=20, description="抖音 配额")
    bing: int = Field(2, ge=1, le=10, description="Bing 配额")
    sogou: int = Field(1, ge=1, le=10, description="搜狗 配额")
    twitterEnabled: bool = Field(True, description="Twitter 是否启用")
    youtubeEnabled: bool = Field(True, description="YouTube 是否启用")
    bilibiliEnabled: bool = Field(True, description="Bilibili 是否启用")
    douyinEnabled: bool = Field(True, description="抖音 是否启用")
    bingEnabled: bool = Field(True, description="Bing 是否启用")
    sogouEnabled: bool = Field(True, description="搜狗 是否启用")
