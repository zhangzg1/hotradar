from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class ProductionConfig(BaseSettings):
    """生产环境配置"""

    # 应用配置
    APP_NAME: str = "AI Hotspot Monitor"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # MySQL 配置
    MYSQL_HOST: str
    MYSQL_PORT: int = 3306
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_DATABASE: str

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
def get_config() -> ProductionConfig:
    return ProductionConfig()