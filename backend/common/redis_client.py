"""
Redis 客户端模块

提供全局单例 RedisClient，所有方法内置优雅降级：
- Redis 未启动或不可用时，读操作返回 None，写操作静默跳过
- 不会影响项目正常运行
"""
import json
from typing import Any, Optional

import redis.asyncio as aioredis

from backend.common.logger import logger
from backend.core.config.development_config import get_config


class RedisClient:
    """异步 Redis 客户端（单例）"""

    def __init__(self):
        self._client: Optional[aioredis.Redis] = None
        self._available: bool = False
        self._initialized: bool = False

    async def init(self):
        """初始化 Redis 连接（仅在首次调用时执行）"""
        if self._initialized:
            return

        try:
            config = get_config()
            self._client = aioredis.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                password=config.REDIS_PASSWORD or None,
                db=config.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            await self._client.ping()
            self._available = True
            logger.info(f"Redis 已连接: {config.REDIS_HOST}:{config.REDIS_PORT}")
        except Exception as e:
            self._available = False
            logger.warning(f"Redis 连接失败，将使用降级模式: {e}")
        finally:
            self._initialized = True

    async def close(self):
        """关闭 Redis 连接"""
        if self._client:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def default_ttl(self) -> int:
        """获取默认缓存 TTL（秒），从配置读取"""
        return get_config().REDIS_CACHE_TTL

    # ==================== 基础操作 ====================

    async def get(self, key: str) -> Optional[str]:
        """获取字符串值"""
        if not self._available:
            return None
        try:
            return await self._client.get(key)
        except Exception:
            return None

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """设置字符串值，ex 为 TTL（秒）"""
        if not self._available:
            return False
        try:
            await self._client.set(key, value, ex=ex)
            return True
        except Exception:
            return False

    async def delete(self, *keys: str) -> bool:
        """删除 key"""
        if not self._available:
            return False
        try:
            await self._client.delete(*keys)
            return True
        except Exception:
            return False

    async def exists(self, key: str) -> bool:
        """检查 key 是否存在"""
        if not self._available:
            return False
        try:
            return await self._client.exists(key) > 0
        except Exception:
            return False

    # ==================== JSON 操作 ====================

    async def get_json(self, key: str) -> Optional[Any]:
        """获取 JSON 反序列化后的值"""
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    async def set_json(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """将对象序列化为 JSON 后存储"""
        try:
            return await self.set(key, json.dumps(value, ensure_ascii=False), ex=ex)
        except (TypeError, ValueError):
            return False

    # ==================== Hash 操作 ====================

    async def hset(self, name: str, mapping: dict) -> bool:
        """设置 Hash 字段"""
        if not self._available:
            return False
        try:
            str_mapping = {str(k): str(v) for k, v in mapping.items()}
            await self._client.hset(name, mapping=str_mapping)
            return True
        except Exception:
            return False

    async def hgetall(self, name: str) -> Optional[dict]:
        """获取 Hash 所有字段"""
        if not self._available:
            return None
        try:
            return await self._client.hgetall(name)
        except Exception:
            return None

    async def hget(self, name: str, key: str) -> Optional[str]:
        """获取 Hash 单个字段"""
        if not self._available:
            return None
        try:
            return await self._client.hget(name, key)
        except Exception:
            return None


# ==================== 全局单例 ====================

_redis_client: Optional[RedisClient] = None


def get_redis() -> RedisClient:
    """获取 Redis 客户端单例"""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


async def init_redis():
    """初始化 Redis 连接（供 lifespan 调用）"""
    client = get_redis()
    await client.init()


async def close_redis():
    """关闭 Redis 连接（供 lifespan 调用）"""
    client = get_redis()
    await client.close()
