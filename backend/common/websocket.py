"""
WebSocket 推送模块
管理 WebSocket 连接和热点推送
"""
import uuid
from typing import Dict, Any, Optional, Set
from datetime import datetime
from fastapi import WebSocket
from backend.common.logger import logger


class ConnectionManager:
    """WebSocket 连接管理器（支持用户隔离）"""

    def __init__(self):
        # 用户ID -> 任务ID -> WebSocket连接集合
        self.user_task_connections: Dict[str, Dict[str, Set[WebSocket]]] = {}
        # 所有活跃连接（向后兼容）
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, task_id: Optional[str] = None, user_id: Optional[str] = None):
        """接受 WebSocket 连接"""
        await websocket.accept()
        self.active_connections.add(websocket)

        if task_id and user_id:
            if user_id not in self.user_task_connections:
                self.user_task_connections[user_id] = {}
            if task_id not in self.user_task_connections[user_id]:
                self.user_task_connections[user_id][task_id] = set()
            self.user_task_connections[user_id][task_id].add(websocket)
            logger.info(f"WebSocket 已连接，用户: {user_id}，订阅任务: {task_id}")

    def disconnect(self, websocket: WebSocket, task_id: Optional[str] = None, user_id: Optional[str] = None):
        """断开 WebSocket 连接"""
        self.active_connections.discard(websocket)

        if task_id and user_id and user_id in self.user_task_connections:
            task_conns = self.user_task_connections[user_id]
            if task_id in task_conns:
                task_conns[task_id].discard(websocket)
                if not task_conns[task_id]:
                    del task_conns[task_id]
                logger.info(f"WebSocket 已断开，用户: {user_id}，取消订阅任务: {task_id}")
            # 清理空的用户条目
            if not task_conns:
                del self.user_task_connections[user_id]

    async def send_to_task(self, task_id: str, user_id: Optional[str], message: Dict[str, Any]):
        """向订阅特定任务的连接发送消息（按用户隔离）"""
        if not user_id or user_id not in self.user_task_connections:
            logger.warning(f"用户 {user_id} 无活跃连接")
            return

        task_conns = self.user_task_connections[user_id]
        if task_id not in task_conns:
            logger.warning(f"任务 {task_id} 用户 {user_id} 无活跃连接")
            return

        disconnected = set()
        for websocket in task_conns[task_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"WebSocket 发送失败: {e}")
                disconnected.add(websocket)

        # 清理断开的连接
        for ws in disconnected:
            self.disconnect(ws, task_id, user_id)

    async def send_to_user(self, user_id: str, message: Dict[str, Any]):
        """广播消息给指定用户的所有连接"""
        if user_id not in self.user_task_connections:
            return

        disconnected = set()
        for task_id, connections in self.user_task_connections[user_id].items():
            for websocket in connections:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"WebSocket 用户广播失败: {e}")
                    disconnected.add(websocket)

        for ws in disconnected:
            self.disconnect(ws, user_id=user_id)

    async def broadcast(self, message: Dict[str, Any]):
        """广播消息给所有连接（向后兼容）"""
        disconnected = set()
        for websocket in self.active_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"WebSocket 广播失败: {e}")
                disconnected.add(websocket)

        for ws in disconnected:
            self.disconnect(ws)


# 全局连接管理器
manager = ConnectionManager()


def generate_task_id() -> str:
    """生成任务ID"""
    return str(uuid.uuid4())


async def get_cached_task_progress(task_id: str) -> Optional[Dict[str, Any]]:
    """
    从 Redis 获取任务进度缓存

    Args:
        task_id: 任务ID

    Returns:
        任务进度字典，Redis 不可用时返回 None
    """
    from backend.common.redis_client import get_redis
    redis = get_redis()
    data = await redis.hgetall(f"task_progress:{task_id}")
    if data:
        return {
            "taskId": task_id,
            "status": data.get("status", "unknown"),
            "totalKeywords": int(data.get("total_keywords", 0)),
            "currentIdx": int(data.get("current_idx", 0)),
            "hotspotsFound": int(data.get("hotspots_found", 0)),
        }
    return None


def build_hotspot_message(
    task_id: str,
    keyword_id: str,
    keyword: str,
    hotspots: list,
    auto_email_triggered: bool = False,
) -> Dict[str, Any]:
    """构建热点推送消息"""

    # 统计各级别数量
    importance_counts = {"urgent": 0, "high": 0, "medium": 0, "low": 0}
    for hotspot in hotspots:
        importance = hotspot.get("importance", "low")
        importance_counts[importance] = importance_counts.get(importance, 0) + 1

    # 构建简要热点信息
    brief_hotspots = []
    for hotspot in hotspots:
        brief_hotspots.append({
            "id": hotspot.get("id"),
            "title": hotspot.get("title"),
            "importance": hotspot.get("importance"),
            "source": hotspot.get("source"),
            "summary": hotspot.get("summary"),
        })

    return {
        "type": "hotspot_batch",
        "data": {
            "taskId": task_id,
            "keywordId": keyword_id,
            "keyword": keyword,
            "hotspots": brief_hotspots,
            "stats": {
                "total": len(hotspots),
                "urgent": importance_counts["urgent"],
                "high": importance_counts["high"],
                "medium": importance_counts["medium"],
                "low": importance_counts["low"],
            },
            "autoEmailTriggered": auto_email_triggered,
            "timestamp": datetime.now().isoformat(),
        },
    }
