# 热点采集工作流

AI 热点监控工具的核心工作流模块，负责从关键词扩展到热点数据入库的完整流程。

## 流程概览

```
关键词扩展 → 多数据源抓取 → URL去重 → 质量过滤 → 时间过滤 → 配额截取 → AI分析过滤 → 数据入库
```

## 文件结构

```
hotspot_collect_agent/
├── config.py      # 配置管理（API Keys、数据源优先级、配额等）
├── state.py       # 状态定义（TypedDict）
├── tools.py       # 数据抓取工具（Twitter/Bing/HN/搜狗/B站/微博）
├── prompt.py      # AI分析提示词模板
├── nodes.py       # 工作流节点实现
├── graph.py       # LangGraph 工作流构建
├── utils.py       # 辅助函数（URL标准化、去重、过滤等）
└── README.md      # 说明文档
```

## 使用方法

### 单次运行

```python
from agents.hotspot_collect_agent import run_workflow

# 运行工作流
result = await run_workflow(
    keyword="Claude Sonnet 4.6",
    keyword_id="uuid-string",
)

print(f"入库数量: {result['savedCount']}")
print(f"扩展关键词: {result['expandedKeywords']}")
```

### 批量运行

```python
from agents.hotspot_collect_agent.graph import run_workflow_batch

keywords = ["Claude Sonnet 4.6", "GPT-5", "DeepSeek V3"]
keyword_ids = ["uuid-1", "uuid-2", "uuid-3"]

results = await run_workflow_batch(keywords, keyword_ids)
```

### 流式运行（调试）

```python
from agents.hotspot_collect_agent.graph import run_workflow_stream

async for event in run_workflow_stream(keyword, keyword_id):
    print(f"节点 {event['node']} 完成")
    print(event['output'])
```

## 配置说明

### 环境变量

在 `.env` 文件中配置：

```bash
# Twitter API（可选，付费）
TWITTER_API_KEY=your_api_key

# LLM API（已有配置）
DS_API_KEY=your_deepseek_key
DS_BASE_URL=https://api.deepseek.com/v1/
```

### 数据源配置

| 数据源 | 方法 | 需要API Key | 频率限制 |
|-------|------|------------|---------|
| Twitter | `fetch_twitter()` | TWITTER_API_KEY | 无 |
| Bing | `fetch_bing()` | 无 | 5秒 |
| HackerNews | `fetch_hackernews()` | 无 | 1秒 |
| 搜狗 | `fetch_sogou()` | 无 | 3秒 |
| Bilibili | `fetch_bilibili()` | 无 | 2秒 |
| 微博 | `fetch_weibo()` | 无 | 3秒 |

### 抓取配额

```python
FETCH_QUOTAS = {
    "twitter": 15,  # Twitter 最多 15 条
    "other": 10,    # 其他来源共享 10 条
}
```

## 工作流节点详解

### 1. 关键词扩展节点

- 使用 LLM (DeepSeek) 将单个关键词扩展为多个变体词
- 扩展规则：大小写变体、核心词拆分、中英文对照
- 结果缓存：同一关键词只调用一次 LLM

### 2. 多数据源抓取节点

- 并行抓取 6 个数据源
- 使用 `asyncio.gather()` 提高效率
- 频率限制器防止被封

### 3. URL去重节点

- URL标准化：移除 `www.`、统一 `https`、移除末尾 `/`
- 保留优先级更高的数据源

### 4. 质量过滤节点

过滤规则：
- title 为空或长度 < 5 → 过滤
- content 为空或长度 < 20 → 过滤
- URL 非法 → 过滤

### 5. 时间过滤节点

- 保留 7 天内的热点
- 无发布时间的暂时保留

### 6. 配额截取节点

- 按数据源优先级排序
- Twitter: 最多 15 条
- 其他来源: 共享 10 条

### 7. AI分析与过滤节点

AI分析：
- 真假识别（`isReal`）
- 相关性评分（`relevance`: 0-100）
- 关键词提及（`keywordMentioned`）
- 重要程度（`importance`: low/medium/high/urgent）
- 摘要生成（`summary`）

三层过滤：
1. `isReal == false` → 过滤
2. `relevance < 50` → 过滤
3. `keywordMentioned == false AND relevance < 65` → 过滤

### 8. 数据入库节点

- 存入 MySQL `hotspots` 表
- 关联 `keywordId`
- 检查唯一约束（URL + source）

## 扩展指南

### 添加新数据源

1. 在 `tools.py` 中添加抓取函数：
```python
async def fetch_new_source(keyword: str, config: Dict) -> List[SearchResult]:
    # 实现抓取逻辑
    return results
```

2. 在 `config.py` 中添加配置：
```python
DEFAULT_FETCH_CONFIG["new_source"] = {"maxResults": 20}
RATE_LIMITS["new_source"] = 3000
SOURCE_PRIORITY["new_source"] = 7
```

3. 在 `tools.fetch_all_sources` 中注册：

### 添加邮箱推送

预留扩展点：在 `save_hotspots_node` 后添加推送节点：

```python
async def email_push_node(state: WorkflowState) -> WorkflowState:
    saved_hotspots = state.get("savedHotspots", [])
    # 实现邮箱推送逻辑
    return state
```

## 依赖说明

```txt
langgraph>=0.2.0       # 工作流编排
aiohttp>=3.9.0         # 异步HTTP
beautifulsoup4>=4.12.0 # HTML解析
lxml>=5.0.0            # HTML解析引擎
tenacity>=8.2.0        # 重试机制
```

## 注意事项

1. **环境隔离**：在 `ai-hotspot-monitor` conda 环境中运行
2. **Twitter API**：需要付费 API Key，未配置时会跳过
3. **LLM 成本**：每条热点分析约消耗 500 tokens
4. **频率限制**：爬虫类数据源有频率限制，避免被封