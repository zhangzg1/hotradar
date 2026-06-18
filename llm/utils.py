import os
from dotenv import load_dotenv

load_dotenv(override=True)

# QWEN ASR 配置（用于音频转文字，保留在 .env 中）
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
QWEN_ASR_BASE_URL = os.getenv("QWEN_ASR_BASE_URL")
