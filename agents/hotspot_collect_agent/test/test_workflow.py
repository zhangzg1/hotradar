"""
热点采集工作流测试（不入库）

逐步执行工作流各节点，打印详细状态，不进行数据入库。

运行方式:
    conda activate ai-hotspot-monitor
    python -m agents.hotspot_collect_agent.test.test_workflow -k "codex"
"""
import asyncio
import sys
import os
import uuid
import time
from datetime import datetime

# 确保项目根目录在路径中
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from agents.hotspot_collect_agent.config import (
    SOURCE_PRIORITY, FETCH_QUOTAS, DEFAULT_FETCH_CONFIG, MAX_AGE_HOURS,
)
from agents.hotspot_collect_agent.state import WorkflowState
from agents.hotspot_collect_agent.nodes import (
    keyword_expansion_node,
    fetch_sources_node,
    url_dedup_node,
    quality_filter_node,
    time_filter_node,
    quota_cutoff_node,
    ai_analysis_node,
)
from agents.hotspot_collect_agent.utils import count_by_source
from backend.common.logger import logger


# ==================== 打印辅助 ====================
def print_header(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_kv(key, value):
    print(f"  {key}: {value}")


def print_source_dist(results):
    counts = count_by_source(results)
    for source, count in sorted(counts.items(), key=lambda x: SOURCE_PRIORITY.get(x[0], 99)):
        p = SOURCE_PRIORITY.get(source, "?")
        print(f"    {source} (优先级 {p}): {count} 条")
    return counts


def print_quota_usage(quota_counts):
    print_kv("twitter", f"{quota_counts.get('twitter', 0)}/{FETCH_QUOTAS.get('twitter', 0)}")
    print_kv("youtube", f"{quota_counts.get('youtube', 0)}/{FETCH_QUOTAS.get('youtube', 0)}")
    bd = quota_counts.get('bilibili', 0) + quota_counts.get('douyin', 0)
    print_kv("bilibili+douyin", f"{bd}/{FETCH_QUOTAS.get('bilibili_douyin', 0)}")
    other = sum(v for k, v in quota_counts.items() if k not in ['twitter', 'youtube', 'bilibili', 'douyin'])
    print_kv("other", f"{other}/{FETCH_QUOTAS.get('other', 0)}")


def print_samples(results, max_count=3):
    if not results:
        print("    (无结果)")
        return
    for i, item in enumerate(results[:max_count], 1):
        title = item.get("title", "")[:55]
        source = item.get("source", "")
        print(f"    [{i}] [{source}] {title}")


# ==================== 逐步执行 ====================
async def run_test(keyword: str):
    start_time = time.time()

    print_header("热点采集工作流测试（不入库）")
    print_kv("关键词", keyword)
    print_kv("开始时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # 初始化状态
    keyword_id = str(uuid.uuid4())
    state: WorkflowState = {
        "keyword": keyword,
        "keywordId": keyword_id,
        "fetchConfig": DEFAULT_FETCH_CONFIG,
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

    def merge(node_output: dict):
        """将节点输出合并到 state"""
        for k, v in node_output.items():
            if k == "stats":
                state["stats"] = {**state.get("stats", {}), **v}
            else:
                state[k] = v

    # ---- 节点 1: 关键词扩展 ----
    print_header("节点 1: 关键词扩展")
    out = await keyword_expansion_node(state)
    merge(out)
    print_kv("扩展关键词数量", f"{len(state['expandedKeywords'])} 个")
    print_kv("关键词列表", state['expandedKeywords'])

    # ---- 节点 2: 多数据源抓取 ----
    print_header("节点 2: 多数据源抓取")
    out = await fetch_sources_node(state)
    merge(out)
    print_kv("总抓取数量", len(state['rawResults']))
    print_source_dist(state['rawResults'])

    # ---- 节点 3: URL 去重 ----
    print_header("节点 3: URL 去重")
    prev = len(state['rawResults'])
    out = await url_dedup_node(state)
    merge(out)
    removed = prev - len(state['uniqueResults'])
    print_kv("去重前", prev)
    print_kv("去重后", len(state['uniqueResults']))
    print_kv("移除重复", removed)
    print_source_dist(state['uniqueResults'])

    # ---- 节点 4: 质量过滤 ----
    print_header("节点 4: 质量过滤")
    prev = len(state['uniqueResults'])
    out = await quality_filter_node(state)
    merge(out)
    removed = prev - len(state['qualityResults'])
    print_kv("过滤前", prev)
    print_kv("过滤后", len(state['qualityResults']))
    print_kv("移除低质量", removed)
    print_source_dist(state['qualityResults'])

    # ---- 节点 5: 时间过滤 ----
    print_header("节点 5: 时间过滤")
    prev = len(state['qualityResults'])
    out = await time_filter_node(state)
    merge(out)
    removed = prev - len(state['freshResults'])
    print_kv("过滤前", prev)
    print_kv("过滤后", len(state['freshResults']))
    print_kv("移除过期", removed)
    print_source_dist(state['freshResults'])

    # ---- 节点 6: 配额截取 ----
    print_header("节点 6: 配额截取")
    prev = len(state['freshResults'])
    out = await quota_cutoff_node(state)
    merge(out)
    removed = prev - len(state['quotaFilteredResults'])
    print_kv("截取前", prev)
    print_kv("截取后", len(state['quotaFilteredResults']))
    print_kv("移除超配额", removed)
    quota_counts = print_source_dist(state['quotaFilteredResults'])
    print_kv("配额配置", FETCH_QUOTAS)
    print_quota_usage(quota_counts)

    # ---- 节点 7: AI 分析 ----
    print_header("节点 7: AI 分析与过滤")
    out = await ai_analysis_node(state)
    merge(out)
    stats = state.get("stats", {})
    print_kv("待分析", stats.get("ai_analyzed", 0))
    print_kv("AI 通过", stats.get("ai_passed", 0))
    print_kv("AI 过滤", stats.get("ai_filtered", 0))
    print_kv("分析失败", stats.get("ai_errors", 0))
    print_kv("已入库跳过", stats.get("already_in_db", 0))
    ai_results = state['aiAnalysisResults']
    if ai_results:
        print("  通过的热点采样:")
        for i, h in enumerate(ai_results[:5], 1):
            print(f"    [{i}] [{h.get('source', '')}] {h.get('title', '')[:55]}")
            print(f"         相关性={h.get('relevance', 0)}  重要程度={h.get('importance', '')}")

    # ---- 节点 8: 入库 — 跳过 ----
    print_header("节点 8: 数据入库（已跳过）")
    print_kv("潜在入库数量", len(ai_results))

    # ---- 汇总 ----
    total_elapsed = time.time() - start_time
    print_header("汇总报告")
    print_kv("关键词", keyword)
    print_kv("总耗时", f"{total_elapsed:.1f}s")
    print()
    print("  流水线:")
    print_kv("  关键词扩展", f"{len(state['expandedKeywords'])} 个变体")
    print_kv("  原始抓取", f"{len(state['rawResults'])} 条")
    print_kv("  URL 去重", f"{len(state['uniqueResults'])} 条")
    print_kv("  质量过滤", f"{len(state['qualityResults'])} 条")
    print_kv("  时间过滤", f"{len(state['freshResults'])} 条")
    print_kv("  配额截取", f"{len(state['quotaFilteredResults'])} 条")
    print_kv("  AI 通过", f"{len(ai_results)} 条")

    raw_counts = count_by_source(state['rawResults'])
    quota_counts = count_by_source(state['quotaFilteredResults'])
    print()
    print("  数据源分布 (原始 -> 配额后):")
    for source in ["twitter", "youtube", "bilibili", "douyin", "bing", "sogou"]:
        print(f"    {source}: {raw_counts.get(source, 0)} -> {quota_counts.get(source, 0)}")

    errors = state.get("errors", [])
    if errors:
        print(f"\n  错误: {errors}")

    print(f"\n{'='*70}")
    print("  测试完成")
    print(f"{'='*70}\n")


# ==================== 主入口 ====================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="热点采集工作流测试（不入库）")
    parser.add_argument("-k", "--keyword", type=str, default="AI Agent", help="测试关键词")
    args = parser.parse_args()

    asyncio.run(run_test(args.keyword))
