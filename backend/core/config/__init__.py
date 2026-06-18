from .development_config import get_config, DevelopmentConfig
from .product_config import ProductionConfig

__all__ = ["get_config", "DevelopmentConfig", "ProductionConfig"]