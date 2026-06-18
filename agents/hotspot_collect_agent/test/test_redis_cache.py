"""
Redis 缓存集成测试

基于 test_workflow.py，测试 Redis 缓存功能：
1. 关键词扩展缓存：首次调 LLM 扩展，第二次从 Redis 命中
2. LLM 分析结果去重：相同 URL 不重复调 LLM
3. 采集任务进度追踪：进度写入 Redis

运行方式:
    conda activate ai-hotspot-monitor
    python -m agents.hotspot_collect_agent.test.test_redis_cache
"""
import asyncio
import sys
import os
import uuid
import time
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from sqlalchemy import create_engine, text

from agents.hotspot_collect_agent.config import SOURCE_PRIORITY, DEFAULT_FETCH_CONFIG
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
from backend.common.redis_client import get_redis
from backend.core.config.development_config import get_config


# ==================== 配置 ====================
TEST_KEYWORD = "claude code"
TEST_USER_ID = "e4f76d75-1b17-4eb7-95c2-d400e4c22990"


# ==================== 从数据库读取配置 ====================
def load_user_config():
    """从数据库读取用户的配额和启用的数据源"""
    config = get_config()
    engine = create_engine(config.DATABASE_URL)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT twitter_enabled, youtube_enabled, bilibili_enabled, "
                 "douyin_enabled, bing_enabled, sogou_enabled, "
                 "twitter, youtube, bilibili, douyin, bing, sogou "
                 "FROM fetch_quota_config WHERE user_id = :uid"),
            {"uid": TEST_USER_ID}
        ).fetchone()

        if not row:
            print(f"[警告] 未找到用户 {TEST_USER_ID} 的配额配置，使用默认值")
            return DEFAULT_FETCH_CONFIG, ["bilibili", "bing", "sogou"]

        enabled_sources = []
        source_names = ["twitter", "youtube", "bilibili", "douyin", "bing", "sogou"]
        for i, name in enumerate(source_names):
            if row[i]:
                enabled_sources.append(name)

        fetch_quotas = {
            "twitter": row[6], "youtube": row[7], "bilibili": row[8],
            "douyin": row[9], "bing": row[10], "sogou": row[11],
            "twitterEnabled": bool(row[0]), "youtubeEnabled": bool(row[1]),
            "bilibiliEnabled": bool(row[2]), "douyinEnabled": bool(row[3]),
            "bingEnabled": bool(row[4]), "sogouEnabled": bool(row[5]),
        }

        print(f"[配置] 启用数据源: {enabled_sources}")
        print(f"[配置] 配额: {', '.join(f'{k}={v}' for k, v in fetch_quotas.items() if not k.endswith('Enabled'))}")

        return fetch_quotas, enabled_sources


# ==================== 打印辅助 ====================
def print_header(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_kv(key, value):
    print(f"  {key}: {value}")


# ==================== 测试主流程 ====================
async def run_test():
    start_time = time.time()

    print_header("Redis 缓存集成测试")
    print_kv("关键词", TEST_KEYWORD)
    print_kv("用户ID", TEST_USER_ID)
    print_kv("开始时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # 初始化 Redis
    redis = get_redis()
    await redis.init()
    print_kv("Redis 可用", redis.available)
    if redis.available:
        print_kv("缓存 TTL", f"{redis.default_ttl}s ({redis.default_ttl // 86400} 天)")

    # 从数据库读取用户配置
    fetch_quotas, enabled_sources = load_user_config()

    # ==================== 测试 1: 关键词扩展缓存 ====================
    print_header("测试 1: 关键词扩展缓存")

    keyword_id = str(uuid.uuid4())
    state: WorkflowState = {
        "keyword": TEST_KEYWORD,
        "keywordId": keyword_id,
        "fetchConfig": DEFAULT_FETCH_CONFIG,
        "fetchQuotas": fetch_quotas,
        "enabledSources": enabled_sources,
        "userId": TEST_USER_ID,
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
        for k, v in node_output.items():
            if k == "stats":
                state["stats"] = {**state.get("stats", {}), **v}
            else:
                state[k] = v

    # 第一次调用：应该触发 LLM
    print("\n  --- 第 1 次调用（应触发 LLM）---")
    t1 = time.time()
    out = await keyword_expansion_node(state)
    merge(out)
    elapsed1 = time.time() - t1
    print_kv("扩展关键词数量", f"{len(state['expandedKeywords'])} 个")
    print_kv("耗时", f"{elapsed1:.2f}s")
    print_kv("缓存标记", state["stats"].get("expansion_cached", False))

    # 检查 Redis 中是否有缓存
    cache_key = f"keyword_expand:{TEST_KEYWORD}"
    redis_cached = await redis.get_json(cache_key)
    print_kv("Redis 缓存命中", redis_cached is not None)
    if redis_cached:
        print_kv("Redis 缓存内容", f"{len(redis_cached)} 个关键词")

    # 第二次调用：应该从 Redis 缓存命中
    print("\n  --- 第 2 次调用（应从 Redis 缓存命中）---")
    # 重新构造 state，清空 expandedKeywords
    state2: WorkflowState = {
        "keyword": TEST_KEYWORD,
        "keywordId": str(uuid.uuid4()),
        "fetchConfig": DEFAULT_FETCH_CONFIG,
        "fetchQuotas": fetch_quotas,
        "enabledSources": enabled_sources,
        "userId": TEST_USER_ID,
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
    t2 = time.time()
    out2 = await keyword_expansion_node(state2)
    for k, v in out2.items():
        if k == "stats":
            state2["stats"] = {**state2.get("stats", {}), **v}
        else:
            state2[k] = v
    elapsed2 = time.time() - t2
    print_kv("扩展关键词数量", f"{len(state2['expandedKeywords'])} 个")
    print_kv("耗时", f"{elapsed2:.2f}s")
    print_kv("缓存标记", state2["stats"].get("expansion_cached", False))

    # 对比
    speedup = elapsed1 / elapsed2 if elapsed2 > 0 else float('inf')
    print(f"\n  [结果] 缓存加速: {speedup:.1f}x (第1次 {elapsed1:.2f}s -> 第2次 {elapsed2:.2f}s)")
    if speedup > 5:
        print("  [通过] Redis 缓存生效，第二次明显更快")
    else:
        print("  [注意] 加速不明显，请检查 Redis 是否正常工作")

    # ==================== 测试 2: 完整工作流 ====================
    print_header("测试 2: 完整工作流（含 LLM 分析缓存）")

    # 节点 2: 数据源抓取
    out = await fetch_sources_node(state)
    merge(out)
    print_kv("总抓取数量", len(state['rawResults']))
    counts = count_by_source(state['rawResults'])
    for s in ["bilibili", "douyin", "bing", "sogou"]:
        print(f"    {s}: {counts.get(s, 0)} 条")

    # 节点 3-6: 过滤
    out = await url_dedup_node(state)
    merge(out)
    out = await quality_filter_node(state)
    merge(out)
    out = await time_filter_node(state)
    merge(out)
    out = await quota_cutoff_node(state)
    merge(out)
    print_kv("配额截取后", len(state['quotaFilteredResults']))

    # 节点 7: AI 分析（首次）
    print("\n  --- AI 分析（首次）---")
    t3 = time.time()
    out = await ai_analysis_node(state)
    merge(out)
    elapsed3 = time.time() - t3
    stats = state.get("stats", {})
    print_kv("待分析", stats.get("ai_analyzed", 0))
    print_kv("AI 通过", stats.get("ai_passed", 0))
    print_kv("AI 过滤", stats.get("ai_filtered", 0))
    print_kv("分析失败", stats.get("ai_errors", 0))
    print_kv("已入库跳过", stats.get("already_in_db", 0))
    print_kv("耗时", f"{elapsed3:.2f}s")

    # 检查 Redis 中是否有分析缓存
    from agents.hotspot_collect_agent.utils import normalize_url
    analysis_cached_count = 0
    for item in state['quotaFilteredResults']:
        url = item.get("url", "")
        if url:
            cache_k = f"analysis_result:{TEST_USER_ID}:{normalize_url(url)}"
            if await redis.exists(cache_k):
                analysis_cached_count += 1
    print_kv("Redis 中分析结果缓存数", analysis_cached_count)

    # ==================== 测试 3: 任务进度追踪 ====================
    print_header("测试 3: 任务进度追踪")

    test_task_id = str(uuid.uuid4())
    progress_key = f"task_progress:{test_task_id}"

    # 模拟任务进度写入
    await redis.hset(progress_key, {
        "status": "running",
        "total_keywords": "3",
        "current_idx": "1",
        "hotspots_found": "5",
    })
    if redis.available:
        try:
            await redis._client.expire(progress_key, 3600)
        except Exception:
            pass

    # 读取进度
    from backend.common.websocket import get_cached_task_progress
    progress = await get_cached_task_progress(test_task_id)
    print_kv("任务 ID", test_task_id)
    print_kv("进度数据", progress)

    if progress and progress.get("status") == "running":
        print("  [通过] 任务进度成功写入并读取")
    else:
        print("  [注意] 任务进度读取失败")

    # 清理测试数据
    await redis.delete(progress_key)
    print("  测试数据已清理")

    # ==================== 汇总 ====================
    total_elapsed = time.time() - start_time
    print_header("测试汇总")
    print_kv("总耗时", f"{total_elapsed:.1f}s")
    print_kv("Redis 状态", "可用" if redis.available else "不可用（降级模式）")
    print(f"\n{'='*70}")
    print("  测试完成")
    print(f"{'='*70}\n")

    await redis.close()


if __name__ == "__main__":
    asyncio.run(run_test())
