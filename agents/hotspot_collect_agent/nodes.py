"""
工作流节点实现
每个节点对应工作流中的一个处理步骤
"""
from typing import Dict, List

from sqlalchemy import select

from .state import WorkflowState, SearchResult, HotspotData
from .config import (
    KEYWORD_EXPANSION_CONFIG,
    FILTER_RULES,
    MAX_AGE_HOURS,
    DEFAULT_FETCH_QUOTAS,
    SOURCE_PRIORITY,
)
from .utils import (
    extract_core_terms,
    parse_json_from_text,
    deduplicate_by_url,
    quality_filter,
    time_filter,
    quota_cutoff,
    pre_match_keyword,
    apply_three_layer_filter,
    normalize_url,
    count_by_source,
    validate_importance,
    parse_datetime,
)
from .tools import fetch_all_sources
from .prompt import (
    KEYWORD_EXPANSION_PROMPT,
    build_analysis_prompt,
    CONTENT_MAX_LENGTH,
    RELEVANCE_REASON_MAX_LENGTH,
    SUMMARY_MAX_LENGTH,
)
from backend.common.mysql import AsyncSessionLocal
from backend.models.hotspot import Hotspot
from backend.common.logger import logger
from backend.common.redis_client import get_redis

# 导入 LLM 轮询服务
from llm.fallback_llm import invoke_with_fallback_async


# ==================== 关键词扩展缓存 ====================
keyword_expansion_cache: Dict[str, List[str]] = {}


# ==================== 节点 1: 关键词扩展 ====================
async def keyword_expansion_node(state: WorkflowState) -> WorkflowState:
    """
    关键词扩展节点

    使用 LLM 将单个关键词扩展为多个变体词

    Args:
        state: 当前工作流状态

    Returns:
        更新后的状态
    """
    keyword = state.get("keyword", "")
    logger.info(f"[节点] 关键词扩展: {keyword}")

    # 检查 Redis 缓存
    redis = get_redis()
    cache_key = f"keyword_expand:{keyword}"
    cached = await redis.get_json(cache_key)
    if cached and isinstance(cached, list):
        logger.info(f"关键词 '{keyword}' Redis 缓存命中")
        keyword_expansion_cache[keyword] = cached
        return {
            "expandedKeywords": cached,
            "stats": {"expansion_cached": True},
        }

    # 检查内存缓存（Redis 不可用时的降级）
    if keyword in keyword_expansion_cache:
        logger.info(f"关键词 '{keyword}' 内存缓存命中")
        return {
            "expandedKeywords": keyword_expansion_cache[keyword],
            "stats": {"expansion_cached": True},
        }

    # 提取核心词 (纯文本方式)
    core_terms = extract_core_terms(keyword)

    try:
        # 构建 LLM 提示词
        min_variants = KEYWORD_EXPANSION_CONFIG.get("min_variants", 5)
        max_variants = KEYWORD_EXPANSION_CONFIG.get("max_variants", 15)

        formatted_prompt = KEYWORD_EXPANSION_PROMPT.format(
            keyword=keyword,
            min_variants=min_variants,
            max_variants=max_variants,
        )

        # 使用轮询机制调用 LLM (异步)
        user_id = state.get("userId")
        content = await invoke_with_fallback_async(formatted_prompt, user_id=user_id)

        # 解析 JSON
        parsed = parse_json_from_text(content)

        if parsed and isinstance(parsed, list):
            # 合并去重
            expanded = list(set([
                keyword,
                *core_terms,
                *[s.strip() for s in parsed if s.strip()],
            ]))
        else:
            # LLM 解析失败，仅使用核心词
            expanded = list(set([keyword, *core_terms]))

        # 缓存结果
        keyword_expansion_cache[keyword] = expanded
        await redis.set_json(cache_key, expanded, ex=redis.default_ttl)

        logger.info(f"关键词扩展完成: {len(expanded)} 个变体")

        return {
            "expandedKeywords": expanded,
            "stats": {"expansion_cached": False, "expansion_count": len(expanded)},
        }

    except Exception as e:
        logger.error(f"关键词扩展失败: {e}")

        # 使用核心词作为 fallback
        expanded = list(set([keyword, *core_terms]))
        keyword_expansion_cache[keyword] = expanded
        await redis.set_json(cache_key, expanded, ex=redis.default_ttl)

        return {
            "expandedKeywords": expanded,
            "errors": [f"关键词扩展失败: {e}"],
        }


# ==================== 节点 2: 多数据源抓取 ====================
async def fetch_sources_node(state: WorkflowState) -> WorkflowState:
    """
    多数据源抓取节点

    并行抓取 Twitter、Bing、HN、搜狗、B站、微博

    Args:
        state: 当前工作流状态

    Returns:
        更新后的状态
    """
    keyword = state.get("keyword", "")
    fetch_config = state.get("fetchConfig", {})
    enabled_sources = state.get("enabledSources", ["twitter", "youtube", "bilibili", "douyin", "bing", "sogou"])
    user_id = state.get("userId")

    logger.info(f"[节点] 多数据源抓取: {keyword}")

    try:
        # 并行抓取所有数据源
        raw_results = await fetch_all_sources(keyword, fetch_config, sources=enabled_sources, user_id=user_id)

        # 统计各数据源数量
        source_counts = count_by_source(raw_results)

        logger.info(f"抓取完成: 共 {len(raw_results)} 条结果")
        logger.info(f"数据源分布: {source_counts}")

        return {
            "rawResults": raw_results,
            "stats": {
                "raw_total": len(raw_results),
                "source_counts": source_counts,
            },
        }

    except Exception as e:
        logger.error(f"数据源抓取失败: {e}")
        return {
            "rawResults": [],
            "errors": [f"数据源抓取失败: {e}"],
        }


# ==================== 节点 3: URL去重 ====================
async def url_dedup_node(state: WorkflowState) -> WorkflowState:
    """
    URL去重节点

    Args:
        state: 当前工作流状态

    Returns:
        更新后的状态
    """
    raw_results = state.get("rawResults", [])

    logger.info(f"[节点] URL去重: {len(raw_results)} 条")

    unique_results = deduplicate_by_url(raw_results)

    removed_count = len(raw_results) - len(unique_results)
    logger.info(f"去重完成: 保留 {len(unique_results)} 条，移除 {removed_count} 条重复")

    return {
        "uniqueResults": unique_results,
        "stats": {
            "unique_total": len(unique_results),
            "dedup_removed": removed_count,
        },
    }


# ==================== 节点 4: 质量过滤 ====================
async def quality_filter_node(state: WorkflowState) -> WorkflowState:
    """
    质量过滤节点

    过滤规则:
    1. title 为空或长度小于 5
    2. content 为空或长度小于 20
    3. URL 非法

    Args:
        state: 当前工作流状态

    Returns:
        更新后的状态
    """
    unique_results = state.get("uniqueResults", [])

    logger.info(f"[节点] 质量过滤: {len(unique_results)} 条")

    quality_results = quality_filter(unique_results)

    removed_count = len(unique_results) - len(quality_results)
    logger.info(f"质量过滤完成: 保留 {len(quality_results)} 条，移除 {removed_count} 条低质量")

    return {
        "qualityResults": quality_results,
        "stats": {
            "quality_total": len(quality_results),
            "quality_removed": removed_count,
        },
    }


# ==================== 节点 5: 时间过滤 ====================
async def time_filter_node(state: WorkflowState) -> WorkflowState:
    """
    时间过滤节点

    保留指定时间范围内的热点 (默认 7 天)

    Args:
        state: 当前工作流状态

    Returns:
        更新后的状态
    """
    quality_results = state.get("qualityResults", [])

    logger.info(f"[节点] 时间过滤: {len(quality_results)} 条")

    fresh_results = time_filter(quality_results, MAX_AGE_HOURS)

    removed_count = len(quality_results) - len(fresh_results)
    logger.info(f"时间过滤完成: 保留 {len(fresh_results)} 条，移除 {removed_count} 条过期")

    return {
        "freshResults": fresh_results,
        "stats": {
            "fresh_total": len(fresh_results),
            "time_removed": removed_count,
        },
    }


# ==================== 节点 6: 配额截取 ====================
async def quota_cutoff_node(state: WorkflowState) -> WorkflowState:
    """
    配额截取节点

    按数据源优先级和用户配置的配额截取结果

    Args:
        state: 当前工作流状态

    Returns:
        更新后的状态
    """
    fresh_results = state.get("freshResults", [])
    fetch_quotas = state.get("fetchQuotas", DEFAULT_FETCH_QUOTAS)

    logger.info(f"[节点] 配额截取: {len(fresh_results)} 条, 配额: {fetch_quotas}")

    quota_results = quota_cutoff(fresh_results, fetch_quotas, SOURCE_PRIORITY)

    removed_count = len(fresh_results) - len(quota_results)
    logger.info(f"配额截取完成: 保留 {len(quota_results)} 条，移除 {removed_count} 条超配额")

    return {
        "quotaFilteredResults": quota_results,
        "stats": {
            "quota_total": len(quota_results),
            "quota_removed": removed_count,
        },
    }


# ==================== 节点 7: AI分析与过滤 ====================
async def ai_analysis_node(state: WorkflowState) -> WorkflowState:
    """
    AI分析与过滤节点

    对每条热点进行 AI 分析，并应用三层过滤

    Args:
        state: 当前工作流状态

    Returns:
        更新后的状态
    """
    quota_results = state.get("quotaFilteredResults", [])
    keyword = state.get("keyword", "")
    expanded_keywords = state.get("expandedKeywords", [])

    logger.info(f"[节点] AI分析: {len(quota_results)} 条待分析")

    # 先检查数据库中已存在的 URL
    user_id = state.get("userId")
    redis = get_redis()
    existing_urls = await _check_existing_urls(quota_results, user_id=user_id)

    # 过滤掉已入库的 - 使用原始URL匹配
    to_analyze = []
    for item in quota_results:
        url = item.get("url", "")  # 使用原始URL
        if url not in existing_urls:
            to_analyze.append(item)

    logger.info(f"数据库检查完成: {len(to_analyze)} 条需AI分析，{len(quota_results) - len(to_analyze)} 条已入库")

    # AI分析
    ai_results: List[HotspotData] = []
    filtered_count = 0
    errors_count = 0

    for item in to_analyze:
        try:
            # 关键词预匹配
            full_text = f"{item.get('title', '')}\n{item.get('content', '')}"
            pre_match = pre_match_keyword(full_text, expanded_keywords)

            # 检查 Redis 中是否已有该 URL 的分析结果（跨关键词去重）
            item_url = item.get("url", "")
            analysis_cache_key = f"analysis_result:{user_id}:{normalize_url(item_url)}"
            cached_analysis = await redis.get_json(analysis_cache_key)

            if cached_analysis:
                analysis = cached_analysis
                logger.debug(f"LLM 分析缓存命中: {item.get('title', '')[:30]}...")
            else:
                # 构建提示词
                analysis_prompt = build_analysis_prompt(keyword, pre_match)

                # 截断内容
                content_for_ai = full_text[:CONTENT_MAX_LENGTH]

                # 构建完整提示词 (system + user)
                full_prompt = f"{analysis_prompt}\n\n内容:\n{content_for_ai}"

                # 使用轮询机制调用 LLM (异步)
                content = await invoke_with_fallback_async(full_prompt, user_id=user_id)

                # 解析 AI 分析结果
                parsed = parse_json_from_text(content)

                if parsed and isinstance(parsed, dict):
                    analysis = {
                        "isReal": bool(parsed.get("isReal", True)),
                        "relevance": max(0, min(100, int(parsed.get("relevance", 0)))),
                        "relevanceReason": str(parsed.get("relevanceReason", ""))[:RELEVANCE_REASON_MAX_LENGTH],
                        "keywordMentioned": bool(parsed.get("keywordMentioned", False)),
                        "importance": validate_importance(parsed.get("importance", "low")),
                        "summary": str(parsed.get("summary", ""))[:SUMMARY_MAX_LENGTH],
                    }
                else:
                    # 解析失败，使用默认值
                    analysis = {
                        "isReal": pre_match.get("matched", False),
                        "relevance": 20 if pre_match.get("matched", False) else 10,
                        "relevanceReason": "AI分析解析失败，使用默认值",
                        "keywordMentioned": pre_match.get("matched", False),
                        "importance": "low",
                        "summary": full_text[:50] + "...",
                    }

                # 缓存分析结果
                await redis.set_json(analysis_cache_key, analysis, ex=redis.default_ttl)

            # 应用三层过滤
            if apply_three_layer_filter(analysis, FILTER_RULES):
                # 合成完整热点数据
                hotspot: HotspotData = {
                    **item,
                    **analysis,
                    "normalizedUrl": normalize_url(item.get("url", "")),
                    "inDatabase": False,
                }
                ai_results.append(hotspot)
            else:
                filtered_count += 1
                logger.debug(f"过滤: {item.get('title', '')[:30]}... (relevance={analysis['relevance']})")

        except Exception as e:
            errors_count += 1
            logger.warning(f"AI分析失败: {e}")

    logger.info(f"AI分析完成: {len(ai_results)} 条通过，{filtered_count} 条被过滤，{errors_count} 条分析失败")

    return {
        "aiAnalysisResults": ai_results,
        "stats": {
            "ai_analyzed": len(to_analyze),
            "ai_passed": len(ai_results),
            "ai_filtered": filtered_count,
            "ai_errors": errors_count,
            "already_in_db": len(quota_results) - len(to_analyze),
        },
    }


async def _check_existing_urls(results: List[SearchResult], user_id: str = None) -> set:
    """
    检查数据库中已存在的 URL

    Args:
        results: 搜索结果列表
        user_id: 用户 ID

    Returns:
        已存在的 URL 集合 (使用原始URL作为key)
    """
    existing_urls = set()

    try:
        async with AsyncSessionLocal() as session:
            for item in results:
                url = item.get("url", "")  # 使用原始URL，不做标准化
                source = item.get("source", "")

                if not url:
                    continue

                # 查询数据库 - 使用原始URL匹配，按用户过滤
                stmt = select(Hotspot).where(
                    Hotspot.url == url,
                    Hotspot.source == source,
                )
                if user_id:
                    stmt = stmt.where(Hotspot.userId == user_id)
                result = await session.execute(stmt)
                hotspot = result.scalar_one_or_none()

                if hotspot:
                    existing_urls.add(url)  # 记录原始URL

    except Exception as e:
        logger.warning(f"数据库检查失败: {e}")

    return existing_urls


# ==================== 节点 8: 数据入库 ====================
async def save_hotspots_node(state: WorkflowState) -> WorkflowState:
    """
    数据入库节点

    将 AI 分析通过的热点数据存入数据库

    Args:
        state: 当前工作流状态

    Returns:
        更新后的状态
    """
    ai_results = state.get("aiAnalysisResults", [])
    keyword_id = state.get("keywordId", "")
    user_id = state.get("userId", "")

    logger.info(f"[节点] 数据入库: {len(ai_results)} 条待入库")

    saved_hotspots: List[HotspotData] = []
    saved_count = 0
    errors_count = 0

    try:
        async with AsyncSessionLocal() as session:
            for item in ai_results:
                try:
                    # 生成热点 ID
                    hotspot_id = str(__import__("uuid").uuid4())

                    # 创建 Hotspot 实例
                    hotspot = Hotspot(
                        id=hotspot_id,
                        userId=user_id,
                        title=item.get("title", ""),
                        content=item.get("content", ""),
                        fullContent=item.get("content", "") if item.get("source") not in ["bilibili", "youtube", "douyin"] else None,
                        url=item.get("url", ""),
                        source=item.get("source", ""),
                        sourceId=item.get("sourceId"),

                        isReal=item.get("isReal", True),
                        relevance=item.get("relevance", 0),
                        relevanceReason=item.get("relevanceReason"),
                        keywordMentioned=item.get("keywordMentioned"),
                        importance=item.get("importance", "low"),
                        summary=item.get("summary"),

                        viewCount=item.get("viewCount"),
                        likeCount=item.get("likeCount"),
                        retweetCount=item.get("retweetCount"),
                        replyCount=item.get("replyCount"),
                        commentCount=item.get("commentCount"),
                        quoteCount=item.get("quoteCount"),
                        danmakuCount=item.get("danmakuCount"),

                        authorName=item.get("author", {}).get("name") if item.get("author") else None,
                        authorUsername=item.get("author", {}).get("username") if item.get("author") else None,
                        authorAvatar=item.get("author", {}).get("avatar") if item.get("author") else None,
                        authorFollowers=item.get("author", {}).get("followers") if item.get("author") else None,
                        authorVerified=item.get("author", {}).get("verified") if item.get("author") else None,

                        publishedAt=parse_datetime(item.get("publishedAt", "")),
                        keywordId=keyword_id,
                    )

                    session.add(hotspot)
                    saved_count += 1

                    # 将热点 ID 添加到 item 中，用于后续邮件通知
                    saved_item = {**item, "id": hotspot_id}
                    saved_hotspots.append(saved_item)

                except Exception as e:
                    errors_count += 1
                    logger.warning(f"入库失败: {item.get('title', '')[:30]}... - {e}")

            # 提交事务
            await session.commit()

        logger.info(f"入库完成: {saved_count} 条成功，{errors_count} 条失败")

    except Exception as e:
        logger.error(f"数据库入库失败: {e}")
        return {
            "errors": [f"数据库入库失败: {e}"],
        }

    return {
        "savedHotspots": saved_hotspots,
        "savedCount": saved_count,
        "filteredCount": len(ai_results) - saved_count,
        "stats": {
            "saved_total": saved_count,
            "save_errors": errors_count,
        },
    }


# ==================== 节点映射 ====================
NODE_FUNCTIONS = {
    "expand_keyword": keyword_expansion_node,
    "fetch_sources": fetch_sources_node,
    "deduplicate": url_dedup_node,
    "quality_filter": quality_filter_node,
    "time_filter": time_filter_node,
    "quota_cutoff": quota_cutoff_node,
    "ai_analysis": ai_analysis_node,
    "save_results": save_hotspots_node,
}