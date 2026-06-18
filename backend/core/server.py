from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from backend.common.mysql import init_db, close_db
from backend.common.logger import logger
from backend.common.websocket import manager
from backend.common.redis_client import init_redis, close_redis
from backend.services.auth_service import verify_token


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("正在启动应用...")

    # 确保所有模型已注册到 Base.metadata，以便 create_all 创建对应的表
    import backend.models  # noqa: F401

    await init_db()

    # 初始化 Redis（连接失败不影响启动）
    await init_redis()

    # 启动调度器并加载持久化配置
    from backend.services.scheduler_service import start_scheduler, load_scheduler_config, stop_scheduler
    start_scheduler()
    await load_scheduler_config()

    yield

    await stop_scheduler()
    await close_redis()
    await close_db()
    logger.info("应用已关闭")


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    app = FastAPI(
        title="AI Hotspot Monitor",
        description="AI 热点监控工具后端服务",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 注册路由
    from backend.api.routers import api_router
    app.include_router(api_router, prefix="/api/v1")

    # WebSocket 路由
    @app.websocket("/ws/tasks/{task_id}")
    async def websocket_task(websocket: WebSocket, task_id: str, token: str = Query(None)):
        """WebSocket 任务订阅端点"""
        # 验证 token 获取用户ID
        if not token:
            await websocket.close(code=4001, reason="Missing authentication token")
            return

        payload = verify_token(token)
        if not payload:
            await websocket.close(code=4001, reason="Invalid or expired token")
            return

        user_id = payload["sub"]

        await manager.connect(websocket, task_id, user_id)
        try:
            # 保持连接，等待服务端推送
            while True:
                # 接收客户端消息（可用于心跳或其他控制）
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            manager.disconnect(websocket, task_id, user_id)
            logger.info(f"WebSocket 断开: user_id={user_id}, task_id={task_id}")

    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    return app
