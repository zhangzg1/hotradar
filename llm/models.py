"""
旧 LLM 实例定义（已废弃，保留仅供测试脚本使用）
用户配置的 LLM 通过 llm/fallback_llm.py 动态创建
"""
from langchain_openai import ChatOpenAI

from .utils import QWEN_API_KEY, QWEN_ASR_BASE_URL

# 仅保留测试用实例
qwen_llm = ChatOpenAI(
    model="qwen-plus",
    temperature=0.8,
    api_key=QWEN_API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
