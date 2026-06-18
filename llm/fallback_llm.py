"""
LLM 调用服务
从数据库读取用户配置的 LLM（Base URL / API Key / 模型名称）动态创建实例
"""
from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, AIMessage
from langchain_openai import ChatOpenAI
import asyncio

from backend.common.logger import logger
from backend.services.settings_service import get_settings, _normalize_base_url


# ==================== 超时配置 ====================
LLM_TIMEOUT_SECONDS = 30


async def _get_user_llm(user_id: str) -> ChatOpenAI:
    """
    从数据库读取用户配置创建 LLM 实例

    Args:
        user_id: 用户 ID

    Returns:
        ChatOpenAI 实例

    Raises:
        RuntimeError: 用户未配置 LLM 或配置不完整
    """
    settings = await get_settings(user_id)
    base_url = settings.get("llmBaseUrl")
    api_key = settings.get("llmApiKey")
    model_name = settings.get("llmModelName")

    if not base_url or not api_key or not model_name:
        raise RuntimeError("LLM 未配置，请先在设置中配置并测试 LLM")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=_normalize_base_url(base_url),
        temperature=0.8,
        timeout=LLM_TIMEOUT_SECONDS,
    )


# ==================== 普通调用 ====================
async def invoke_with_fallback_async(prompt: str, timeout: int = LLM_TIMEOUT_SECONDS, user_id: str = None, **kwargs) -> str:
    """
    异步调用用户配置的 LLM

    Args:
        prompt: 提示词
        timeout: 超时时间（秒）
        user_id: 用户 ID

    Returns:
        LLM 响应内容
    """
    llm = await _get_user_llm(user_id)
    model_name = llm.model_name

    try:
        logger.info(f"[LLM] 使用 {model_name} 调用")
        response = await asyncio.wait_for(
            llm.ainvoke(prompt, **kwargs),
            timeout=timeout,
        )

        if response and hasattr(response, "content"):
            logger.info(f"[LLM] {model_name} 调用成功")
            return response.content

        raise RuntimeError("模型返回了空响应")

    except asyncio.TimeoutError:
        raise RuntimeError(f"LLM 调用超时 ({timeout}s)")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"LLM 调用失败: {e}")


# ==================== Tool Calling ====================
async def invoke_with_tools_fallback_async(
    messages: List[BaseMessage],
    tools: List[Dict[str, Any]],
    timeout: int = LLM_TIMEOUT_SECONDS,
    user_id: str = None,
    **kwargs,
) -> AIMessage:
    """
    异步调用用户配置的 LLM（带 Tool Calling）

    Args:
        messages: LangChain 消息列表
        tools: Tool schema 列表
        timeout: 超时时间（秒）
        user_id: 用户 ID

    Returns:
        AIMessage 响应（包含 tool_calls 信息）
    """
    llm = await _get_user_llm(user_id)
    model_name = llm.model_name

    try:
        logger.info(f"[LLM-Tool] 使用 {model_name} 调用")
        llm_with_tools = llm.bind_tools(tools)

        response = await asyncio.wait_for(
            llm_with_tools.ainvoke(messages, **kwargs),
            timeout=timeout,
        )

        if response:
            logger.info(f"[LLM-Tool] {model_name} 调用成功")
            return response

        raise RuntimeError("模型返回了空响应")

    except asyncio.TimeoutError:
        raise RuntimeError(f"LLM (Tool Calling) 调用超时 ({timeout}s)")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"LLM (Tool Calling) 调用失败: {e}")


# ==================== 流式调用 ====================
async def stream_with_user_llm(messages: List[BaseMessage], user_id: str = None):
    """
    使用用户配置的 LLM 进行流式输出

    Args:
        messages: LangChain 消息列表
        user_id: 用户 ID

    Yields:
        内容片段
    """
    llm = await _get_user_llm(user_id)
    model_name = llm.model_name

    logger.info(f"[LLM-Stream] 使用 {model_name} 流式输出")

    async for chunk in llm.astream(messages):
        if chunk.content:
            yield chunk.content

    logger.info(f"[LLM-Stream] {model_name} 流式输出完成")
