"""
AI分析提示词模板
包含关键词扩展和内容分析的核心提示词
"""


# ==================== 关键词扩展提示词 ====================
KEYWORD_EXPANSION_PROMPT = """你是一个关键词扩展专家。你的任务是将用户输入的一个关键词扩展为多个相关的变体词，以提高搜索召回率。

输入关键词: {keyword}

扩展规则:
1. 包含原始关键词的各种写法（大小写、空格、连字符变体）
2. 包含关键词的核心组成词（拆分后的各个有意义的词）
3. 包含常见别称、缩写、中英文对照
4. 不要加入泛化词（比如关键词是"Claude Sonnet 4.6"，不要加"AI模型"这种泛化词）
5. 总数控制在 {min_variants}-{max_variants} 个

输出 JSON 数组，只输出 JSON，不要有其他内容。

示例:
输入: "Claude Sonnet 4.6"
输出: ["Claude Sonnet 4.6", "Claude Sonnet", "Sonnet 4.6", "claude-sonnet-4.6", "Claude 4.6", "Anthropic Sonnet"]
"""


# ==================== 内容分析提示词 ====================
def build_analysis_prompt(keyword: str, pre_match_result: dict) -> str:
    """
    构建内容分析提示词

    Args:
        keyword: 原始关键词
        pre_match_result: 预匹配结果 {"matched": bool, "matchedTerms": list}

    Returns:
        构建好的提示词
    """
    matched = pre_match_result.get("matched", False)
    matched_terms = pre_match_result.get("matchedTerms", [])

    if matched:
        match_hint = f"\n注意：文本预匹配发现内容中包含以下关键词变体：{', '.join(matched_terms)}"
    else:
        match_hint = f'\n注意：文本预匹配发现内容中未直接提及关键词"{keyword}"的任何变体，请特别严格审核相关性。'

    return f"""你是一个热点内容精准匹配专家。你的任务是判断一段内容是否与指定的监控关键词【{keyword}】直接相关。

{match_hint}

分析要点:
1. 判断是否为真实有价值的信息（排除标题党、假新闻、营销软文）
2. 判断内容是否【直接】涉及关键词"{keyword}"。注意:
   - 仅仅属于同一领域但未提及关键词的内容，相关性应低于 40 分
   - 内容必须直接讨论、提及或与"{keyword}"有实质关联才能获得 60 分以上
   - 只是间接沾边（如同类产品、同领域但不同主题）应给 30-50 分
3. 判断内容中是否直接提及了"{keyword}"或其等价表述
4. 评估热点的重要程度（对关注"{keyword}"的人来说有多重要）
5. 用一句话说明此内容与"{keyword}"的关系（不是介绍内容本身，而是说"此内容与关键词的关联是什么"）
6. 用一句话解释你的相关性打分理由

请以 JSON 格式输出:
 {{
   "isReal": true/false,
   "relevance": 0-100,
   "relevanceReason": "相关性打分理由...",
   "keywordMentioned": true/false,
   "importance": "low/medium/high/urgent",
   "summary": "此内容与【{keyword}】的关联：..."
 }}

只输出 JSON，不要有其他内容。"""


# ==================== 关键词核心词提取提示词 ====================
def extract_core_terms_prompt(keyword: str) -> str:
    """
    构建核心词提取提示词（备用，主要使用纯文本方式）

    Args:
        keyword: 原始关键词

    Returns:
        构建好的提示词
    """
    return f"""请从以下关键词中提取核心组成词（拆分后的各个有意义的词）:

关键词: {keyword}

输出 JSON 数组，只输出 JSON，不要有其他内容。

示例:
输入: "Claude Sonnet 4.6"
输出: ["Claude", "Sonnet", "4.6", "Claude Sonnet", "Sonnet 4.6"]
"""


# ==================== 提示词常量 ====================
CONTENT_MAX_LENGTH = 2000  # 内容截断长度
RELEVANCE_REASON_MAX_LENGTH = 200  # 相关性理由最大长度
SUMMARY_MAX_LENGTH = 150  # 摘要最大长度