"""
工作流图构建
使用 LangGraph 构建热点采集工作流
"""
from typing import Dict, Any, Optional, List

from langgraph.graph import StateGraph, END

from .state import WorkflowState, FetchStats
from .nodes import NODE_FUNCTIONS
from .config import DEFAULT_FETCH_CONFIG, DEFAULT_FETCH_QUOTAS, DEFAULT_ENABLED_SOURCES
from backend.common.logger import logger


# ==================== 构建工作流图 ====================
def build_workflow_graph() -> StateGraph:
    """
    构建热点采集工作流图

    Returns:
        StateGraph 实例
    """
    # 创建状态图
    workflow = StateGraph(WorkflowState)

    # 添加节点
    workflow.add_node("expand_keyword", NODE_FUNCTIONS["expand_keyword"])
    workflow.add_node("fetch_sources", NODE_FUNCTIONS["fetch_sources"])
    workflow.add_node("deduplicate", NODE_FUNCTIONS["deduplicate"])
    workflow.add_node("quality_filter", NODE_FUNCTIONS["quality_filter"])
    workflow.add_node("time_filter", NODE_FUNCTIONS["time_filter"])
    workflow.add_node("quota_cutoff", NODE_FUNCTIONS["quota_cutoff"])
    workflow.add_node("ai_analysis", NODE_FUNCTIONS["ai_analysis"])
    workflow.add_node("save_results", NODE_FUNCTIONS["save_results"])

    # 定义边（顺序执行）
    workflow.add_edge("expand_keyword", "fetch_sources")
    workflow.add_edge("fetch_sources", "deduplicate")
    workflow.add_edge("deduplicate", "quality_filter")
    workflow.add_edge("quality_filter", "time_filter")
    workflow.add_edge("time_filter", "quota_cutoff")
    workflow.add_edge("quota_cutoff", "ai_analysis")
    workflow.add_edge("ai_analysis", "save_results")
    workflow.add_edge("save_results", END)

    # 设置入口
    workflow.set_entry_point("expand_keyword")

    return workflow


# ==================== 工作流运行入口 ====================
async def run_workflow(
    keyword: str,
    keyword_id: str,
    fetch_config: Optional[Dict[str, Any]] = None,
    fetch_quotas: Optional[Dict[str, int]] = None,
    enabled_sources: Optional[List[str]] = None,
    user_id: str = None,
) -> Dict[str, Any]:
    """
    运行热点采集工作流

    Args:
        keyword: 监控关键词
        keyword_id: 关键词ID
        fetch_config: 抓取配置 (可选)
        fetch_quotas: 各数据源配额 (可选)
        enabled_sources: 启用的数据源列表 (可选)
        user_id: 用户ID

    Returns:
        工作流执行结果
    """
    logger.info(f"========== 开始热点采集工作流 ==========")
    logger.info(f"关键词: {keyword}")
    logger.info(f"关键词ID: {keyword_id}")

    # 初始化状态
    initial_state: WorkflowState = {
        "keyword": keyword,
        "keywordId": keyword_id,
        "userId": user_id,
        "fetchConfig": fetch_config or DEFAULT_FETCH_CONFIG,
        "fetchQuotas": fetch_quotas or DEFAULT_FETCH_QUOTAS,
        "enabledSources": enabled_sources or DEFAULT_ENABLED_SOURCES,
        "expandedKeywords": [],
        "rawResults": [],
        "uniqueResults": [],
        "qualityResults": [],
        "freshResults": [],
        "quotaFilteredResults": [],
        "aiAnalysisResults": [],
        "savedHotspots": [],
        "savedCount": 0,
        "filteredCount": 0,
        "errors": [],
        "stats": {},
    }

    # 构建并编译工作流
    workflow = build_workflow_graph()
    app = workflow.compile()

    # 运行工作流
    try:
        final_state = await app.ainvoke(initial_state)

        # 汇总结果
        result = {
            "keyword": keyword,
            "keywordId": keyword_id,
            "expandedKeywords": final_state.get("expandedKeywords", []),
            "savedCount": final_state.get("savedCount", 0),
            "savedHotspots": final_state.get("savedHotspots", []),
            "errors": final_state.get("errors", []),
            "stats": _build_stats(final_state),
        }

        logger.info(f"========== 工作流完成 ==========")
        logger.info(f"入库数量: {result['savedCount']}")
        logger.info(f"扩展关键词: {len(result['expandedKeywords'])} 个")

        return result

    except Exception as e:
        logger.error(f"工作流执行失败: {e}")
        return {
            "keyword": keyword,
            "keywordId": keyword_id,
            "savedCount": 0,
            "errors": [f"工作流执行失败: {e}"],
        }


def _build_stats(state: WorkflowState) -> FetchStats:
    """
    构建统计信息

    Args:
        state: 工作流最终状态

    Returns:
        FetchStats 统计信息
    """
    stats = state.get("stats", {})
    raw_results = state.get("rawResults", [])

    # 计算各数据源数量
    from .utils import count_by_source
    source_counts = count_by_source(raw_results)

    return {
        "twitter_count": source_counts.get("twitter", 0),
        "youtube_count": source_counts.get("youtube", 0),
        "bilibili_count": source_counts.get("bilibili", 0),
        "douyin_count": source_counts.get("douyin", 0),
        "bing_count": source_counts.get("bing", 0),
        "sogou_count": source_counts.get("sogou", 0),
        "total_raw": len(raw_results),
        "total_unique": stats.get("unique_total", len(state.get("uniqueResults", []))),
        "total_quality": stats.get("quality_total", len(state.get("qualityResults", []))),
        "total_fresh": stats.get("fresh_total", len(state.get("freshResults", []))),
        "total_quota": stats.get("quota_total", len(state.get("quotaFilteredResults", []))),
        "total_ai_analyzed": stats.get("ai_analyzed", 0),
        "total_saved": stats.get("saved_total", 0),
        "total_filtered": stats.get("ai_filtered", 0),
    }


# ==================== 批量运行入口 ====================
async def run_workflow_batch(
    keywords: list,
    keyword_ids: list,
    fetch_config: Optional[Dict[str, Any]] = None,
    fetch_quotas: Optional[Dict[str, int]] = None,
    enabled_sources: Optional[List[str]] = None,
    user_id: str = None,
) -> list:
    """
    批量运行热点采集工作流

    Args:
        keywords: 关键词列表
        keyword_ids: 关键词ID列表
        fetch_config: 抓取配置 (可选)
        fetch_quotas: 各数据源配额 (可选)
        enabled_sources: 启用的数据源列表 (可选)
        user_id: 用户ID

    Returns:
        各关键词的工作流执行结果列表
    """
    logger.info(f"========== 批量热点采集 ==========")
    logger.info(f"关键词数量: {len(keywords)}")

    results = []

    for i, (keyword, keyword_id) in enumerate(zip(keywords, keyword_ids)):
        logger.info(f"处理第 {i+1}/{len(keywords)} 个关键词: {keyword}")

        result = await run_workflow(keyword, keyword_id, fetch_config, fetch_quotas, enabled_sources, user_id=user_id)
        results.append(result)

    # 汇总统计
    total_saved = sum(r.get("savedCount", 0) for r in results)
    logger.info(f"========== 批量采集完成 ==========")
    logger.info(f"总入库数量: {total_saved}")

    return results


# ==================== 流式运行入口 (用于调试) ====================
async def run_workflow_stream(
    keyword: str,
    keyword_id: str,
    fetch_config: Optional[Dict[str, Any]] = None,
    fetch_quotas: Optional[Dict[str, int]] = None,
    enabled_sources: Optional[List[str]] = None,
    user_id: str = None,
):
    """
    流式运行热点采集工作流 (返回每个节点的中间状态)

    Args:
        keyword: 监控关键词
        keyword_id: 关键词ID
        fetch_config: 抓取配置 (可选)
        fetch_quotas: 各数据源配额 (可选)
        enabled_sources: 启用的数据源列表 (可选)
        user_id: 用户ID

    Yields:
        各节点执行后的状态更新
    """
    logger.info(f"========== 流式热点采集工作流 ==========")
    logger.info(f"关键词: {keyword}")

    # 初始化状态
    initial_state: WorkflowState = {
        "keyword": keyword,
        "keywordId": keyword_id,
        "userId": user_id,
        "fetchConfig": fetch_config or DEFAULT_FETCH_CONFIG,
        "fetchQuotas": fetch_quotas or DEFAULT_FETCH_QUOTAS,
        "enabledSources": enabled_sources or DEFAULT_ENABLED_SOURCES,
        "expandedKeywords": [],
        "rawResults": [],
        "uniqueResults": [],
        "qualityResults": [],
        "freshResults": [],
        "quotaFilteredResults": [],
        "aiAnalysisResults": [],
        "savedHotspots": [],
        "savedCount": 0,
        "filteredCount": 0,
        "errors": [],
        "stats": {},
    }

    # 构建并编译工作流
    workflow = build_workflow_graph()
    app = workflow.compile()

    # 流式执行
    try:
        async for event in app.astream(initial_state):
            node_name = list(event.keys())[0]
            node_output = event[node_name]
            logger.info(f"[流式] 节点 {node_name} 完成")
            yield {"node": node_name, "output": node_output}

    except Exception as e:
        logger.error(f"流式工作流执行失败: {e}")
        yield {"error": str(e)}