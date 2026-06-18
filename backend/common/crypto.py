"""
对称加密工具
使用 Fernet (AES-128-CBC) 加密敏感配置（如 API Key）
"""
import os
from pathlib import Path
from cryptography.fernet import Fernet

from backend.common.logger import logger

_ENV_KEY_NAME = "SETTINGS_ENCRYPTION_KEY"
_PROJECT_ROOT = Path(__file__).parent.parent.parent


def _get_or_create_key() -> bytes:
    """
    从 .env 获取加密密钥，不存在则自动生成并写入
    """
    key = os.getenv(_ENV_KEY_NAME)
    if key:
        return key.encode()

    # 尝试手动加载 .env 文件
    try:
        from dotenv import load_dotenv
        load_dotenv(_PROJECT_ROOT / ".env")
        key = os.getenv(_ENV_KEY_NAME)
        if key:
            return key.encode()
    except ImportError:
        pass

    # 自动生成密钥
    new_key = Fernet.generate_key().decode()
    env_path = os.path.join(os.getcwd(), ".env")

    try:
        with open(env_path, "a", encoding="utf-8") as f:
            f.write(f"\n{_ENV_KEY_NAME}={new_key}\n")
        logger.info(f"已自动生成 {_ENV_KEY_NAME} 并写入 .env")
    except Exception as e:
        logger.warning(f"无法写入 .env: {e}，使用临时密钥（重启后失效）")

    return new_key.encode()


_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_get_or_create_key())
    return _fernet


def encrypt(plaintext: str) -> str:
    """加密明文，返回 Base64 编码的密文"""
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """解密密文，返回明文"""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except Exception as e:
        logger.error(f"解密失败: {e}")
        return ""


def mask_key(key: str) -> str:
    """遮盖 Key，仅显示末 4 位"""
    if not key or len(key) <= 4:
        return "****"
    return f"****{key[-4:]}"
