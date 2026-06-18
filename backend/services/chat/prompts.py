"""
聊天系统提示词构建
"""

SYSTEM_PROMPT_TEMPLATE = """你是一名热点分析助手，负责帮助用户深入理解和探索热点内容。

### 一、当前热点基本信息

* 标题：{title}
* 来源：{source}
* 关键词：{keyword}
* AI 摘要：{summary}

### 二、当前热点原文内容

{full_content}

### 三、同关键词下的其他热点概览（共 {other_count} 条）

{other_hotspots_summary}

### 四、工具使用说明

当用户的问题需要参考其他热点的详细内容时，可调用 `load_hotspot_detail` 工具获取对应热点的完整原文信息。

### 五、回复策略说明

在默认情况下，用户的提问均基于**当前热点内容**展开，你应优先依赖当前热点的信息及其原文进行回答。

如果当前热点内容无法充分支撑用户问题，那么应该执行以下判断流程：
1. 查阅"同关键词下的其他热点概览"；
2. 判断这些热点是否能够为回答提供有效补充；
3. 若可以提供帮助，则调用工具获取对应热点的详细内容后再进行回答；
4. 若帮助有限，则基于已有信息与通用知识，进行合理且礼貌的补充说明。

### 六、注意事项

1. 优先基于当前热点内容进行回答；
2. 如需引用其他热点，必须先获取其完整内容后再使用；
3. 回答应保持准确、客观，如引用原文需明确标注来源；
4. 全程使用中文进行回复。
"""


def build_system_prompt(
    hotspot_info: dict,
    full_content: str,
    other_hotspots: list,
    keyword: str = "",
) -> str:
    """
    构建系统提示词

    Args:
        hotspot_info: 当前热点基本信息
        full_content: 完整原文内容
        other_hotspots: 同关键词其他热点概览列表
        keyword: 关键词文本

    Returns:
        系统提示词字符串
    """
    # 构建其他热点概览
    other_summary_lines = []
    for i, h in enumerate(other_hotspots[:20], 1):  # 最多显示20条概览
        title = h.get("title", "")[:50]
        summary = h.get("summary", "")[:100] if h.get("summary") else ""
        source = h.get("source", "")
        other_summary_lines.append(f"{i}. [{source}] {title}\n   摘要: {summary}\n   ID: {h.get('id')}")

    other_summary = "\n".join(other_summary_lines) if other_summary_lines else "暂无其他相关热点"

    # 构建完整提示词
    return SYSTEM_PROMPT_TEMPLATE.format(
        title=hotspot_info.get("title", ""),
        source=hotspot_info.get("source", ""),
        keyword=keyword or hotspot_info.get("keyword", "未知"),
        summary=hotspot_info.get("summary", "无"),
        full_content=full_content[:3000] if full_content else "无完整内容",  # 截断防止过长
        other_count=len(other_hotspots),
        other_hotspots_summary=other_summary,
    )