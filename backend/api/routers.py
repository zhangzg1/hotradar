from fastapi import APIRouter
from backend.api.v1 import auth, hotspots, keywords, collection, email, chat, scheduler, fetch_quota, settings, douyin_cookie

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(hotspots.router, prefix="/hotspots", tags=["hotspots"])
api_router.include_router(chat.router, prefix="/hotspots", tags=["chat"])
api_router.include_router(keywords.router, prefix="/keywords", tags=["keywords"])
api_router.include_router(collection.router, prefix="/collections", tags=["collections"])
api_router.include_router(email.router, prefix="/email-notifications", tags=["email-notifications"])
api_router.include_router(scheduler.router, prefix="/scheduler", tags=["scheduler"])
api_router.include_router(fetch_quota.router, prefix="/fetch-quotas", tags=["fetch-quotas"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(douyin_cookie.router, prefix="/douyin-cookie", tags=["douyin-cookie"])