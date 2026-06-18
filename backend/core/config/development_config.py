from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class DevelopmentConfig(BaseSettings):
    """开发环境配置"""

    # 应用配置
    APP_NAME: str = "AI Hotspot Monitor"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # MySQL 配置
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "ai_hotspot_monitor"

    # Redis 配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_CACHE_TTL: int = 604800  # 缓存有效期（秒），默认 7 天

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_config() -> DevelopmentConfig:
    return DevelopmentConfig()