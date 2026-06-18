"""请求体模块"""
from backend.schemas.request.collection import CollectionRequest
from backend.schemas.request.email import EmailNotificationRequest
from backend.schemas.request.keyword import (
    KeywordCreateRequest,
    KeywordUpdateRequest,
    KeywordBatchRequest,
    BatchAction,
)
from backend.schemas.request.hotspot import HotspotSearchRequest
from backend.schemas.request.chat import ChatRequest
from backend.schemas.request.scheduler import SchedulerConfigRequest
from backend.schemas.request.fetch_quota import FetchQuotaRequest

__all__ = [
    "CollectionRequest",
    "EmailNotificationRequest",
    "KeywordCreateRequest",
    "KeywordUpdateRequest",
    "KeywordBatchRequest",
    "BatchAction",
    "HotspotSearchRequest",
    "ChatRequest",
    "SchedulerConfigRequest",
    "FetchQuotaRequest",
]