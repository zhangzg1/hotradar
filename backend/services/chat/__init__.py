"""
热点问答聊天服务包
支持流式输出
"""
from .service import process_chat, process_chat_stream, get_or_create_session
from .prompts import build_system_prompt

__all__ = ["process_chat", "process_chat_stream", "get_or_create_session", "build_system_prompt"]