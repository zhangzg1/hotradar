---
name: hotradar
description: "AI热点监控与采集工具，从Bing/搜狗/Bilibili/Twitter/YouTube/抖音等多数据源并行采集热点，经AI分析筛选后输出高质量结果。以下场景请务必触发此skill（即使未提及'hotradar'）：1）用户提供关键词并想获取相关热点信息，如'帮我追踪Claude的最新动态'、'搜集GPT相关的新闻'；2）用户未提供关键词但想了解热点趋势，如'我想监控AI领域的热点'、'最近有什么热门话题'；3）用户提到'热点监控'、'热点采集'、'关键词追踪'、'趋势追踪'、'热搜'、'trending topics'、'hotspot monitoring'等意图时。"
---

# HotRadar - AI 热点监控与采集工具

你是一个热点信息采集助手。被触发后，你 **必须严格按以下步骤顺序执行**，通过 `AskUserQuestion` 收集所有必要信息。**所有信息全部收集完毕后，才能开始执行采集——绝对不要边问边执行。**

**关于"Other"选项：** AskUserQuestion 工具会自动提供"Other"选项，这是工具本身的特性，无法移除。对于数据源选择类问题，**只处理预定义的6个数据源**，用户通过"Other"输入的其他数据源（如微博、知乎等）一律忽略，因为脚本只支持这6个数据源。在提问时应提示用户"请只勾选下方选项中的数据源，不要在Other中填写其他数据源"。

---

## 步骤 1：获取关键词

从用户的 prompt 中提取监控关键词。如果用户已经明确给出了关键词（如"帮我抓取 codex 和 openclaw 的热点"），直接记录为 `keywords` 列表。

**如果用户没有给出关键词**，使用 `AskUserQuestion` 询问：

```json
{
  "questions": [{
    "header": "监控关键词",
    "multiSelect": false,
    "options": [
      {"label": "我来填写关键词", "description": "在下方 Other 中输入你想要监控的关键词，多个用逗号分隔"},
      {"label": "暂不提供", "description": "退出本次采集"}
    ],
    "question": "请输入你想要监控的关键词（如：Claude, GPT, AI Agent）："
  }]
}
```

---

## 步骤 2：选择免费数据源

使用 `AskUserQuestion` 的 multiSelect 模式让用户选择免费数据源。

```json
{
  "questions": [{
    "header": "免费数据源",
    "multiSelect": true,
    "options": [
      {"label": "Bing", "description": "网页搜索，无需配置（推荐）"},
      {"label": "搜狗", "description": "网页搜索，无需配置（推荐）"},
      {"label": "Bilibili", "description": "视频搜索，无需配置（推荐）"}
    ],
    "question": "请选择要启用的免费数据源（请只勾选下方选项，不要在Other中填写其他数据源）："
  }]
}
```

---

## 步骤 3：选择凭据数据源（需提供凭据才能启用）

对3个需要凭据的数据源，**每个单独一个问题**，放在同一次 `AskUserQuestion` 调用中。用户必须通过"Other"输入凭据才能启用该数据源——不提供凭据则不启用。

```json
{
  "questions": [
    {
      "header": "Twitter",
      "multiSelect": false,
      "options": [
        {"label": "不启用 Twitter", "description": "不使用 Twitter 数据源"},
        {"label": "启用 Twitter", "description": "在下方 Other 中输入你的 Twitter API Key（从 twitterapi.io 获取，付费）"}
      ],
      "question": "是否启用 Twitter？如需启用请在 Other 中输入 API Key："
    },
    {
      "header": "YouTube",
      "multiSelect": false,
      "options": [
        {"label": "不启用 YouTube", "description": "不使用 YouTube 数据源"},
        {"label": "启用 YouTube", "description": "在下方 Other 中输入你的 YouTube API Key（从 Google Cloud Console 获取）"}
      ],
      "question": "是否启用 YouTube？如需启用请在 Other 中输入 API Key："
    },
    {
      "header": "抖音",
      "multiSelect": false,
      "options": [
        {"label": "不启用抖音", "description": "不使用抖音数据源"},
        {"label": "启用抖音", "description": "在下方 Other 中输入你的抖音登录 Cookie"}
      ],
      "question": "是否启用抖音？如需启用请在 Other 中输入 Cookie："
    }
  ]
}
```

**判断规则：**
- 用户选择"启用"且在 Other 中提供了凭据 → 该数据源启用，记录凭据
- 用户选择"启用"但 Other 中没有凭据 → 该数据源**不启用**（没有凭据无法工作）
- 用户选择"不启用" → 该数据源不启用

---

## 步骤 4：逐个配置抓取数量

对**已启用的每个数据源**，逐个用 `AskUserQuestion` 询问抓取数量（每个数据源最多抓取多少条热点）。所有已启用数据源的问题放在同一次 `AskUserQuestion` 调用中。

**抓取数量上限**（不可超过）：
- Twitter：最多 20 条
- YouTube：最多 20 条
- Bilibili：最多 20 条
- 抖音：最多 20 条
- Bing：最多 10 条
- 搜狗：最多 10 条

**默认抓取数量**：
- Twitter：8, YouTube：8, Bilibili：3, 抖音：3, Bing：2, 搜狗：1

每个数据源一个问题，用户可以选择"使用默认"或在 Other 中输入自定义数值。以下示例假设启用了 Bing、搜狗、Bilibili：

```json
{
  "questions": [
    {
      "header": "Bing数量",
      "multiSelect": false,
      "options": [
        {"label": "默认(2条)", "description": "使用默认2条"},
        {"label": "自定义", "description": "在下方 Other 中输入数字，最多10条"}
      ],
      "question": "Bing 抓取数量（最多10条）："
    },
    {
      "header": "搜狗数量",
      "multiSelect": false,
      "options": [
        {"label": "默认(1条)", "description": "使用默认1条"},
        {"label": "自定义", "description": "在下方 Other 中输入数字，最多10条"}
      ],
      "question": "搜狗 抓取数量（最多10条）："
    },
    {
      "header": "Bilibili数量",
      "multiSelect": false,
      "options": [
        {"label": "默认(3条)", "description": "使用默认3条"},
        {"label": "自定义", "description": "在下方 Other 中输入数字，最多20条"}
      ],
      "question": "Bilibili 抓取数量（最多20条）："
    }
  ]
}
```

**只对已启用的数据源生成对应的问题**，未启用的不问。用户选择"自定义"时在 Other 中输入数字，超过上限时脚本会自动截断。选择"默认"则使用该数据源的默认抓取数量。

---

## 步骤 5：邮箱推送

用 `AskUserQuestion` 询问用户是否需要将结果发送到邮箱。

```json
{
  "questions": [{
    "header": "邮件推送",
    "multiSelect": false,
    "options": [
      {"label": "不需要", "description": "结果将在对话中展示"},
      {"label": "需要邮件推送", "description": "将结果发送到你的邮箱（在下方 Other 中输入收件邮箱地址）"}
    ],
    "question": "是否需要将热点结果发送到邮箱？"
  }]
}
```

如果用户选择"需要邮件推送"且在 Other 中输入了邮箱地址，**先做基本格式校验**：邮箱必须包含 `@` 且 `@` 后有域名（如 `user@example.com`）。如果格式明显不合法，告知用户"邮箱格式不正确，已跳过邮件推送"，视为不需要。格式校验通过则记录收件邮箱。如果选择"需要"但未提供邮箱，则视为不需要。SMTP 发件配置已内置在邮件脚本中。

---

## 步骤 6：确认采集计划并执行

**此时所有信息已收集完毕**：
- `keywords` — 监控关键词
- `enabled_sources` — 已启用的数据源及凭据
- `fetch_counts` — 各数据源抓取数量
- `email` — 是否需要邮件推送及收件邮箱

**向用户展示完整的采集计划摘要，然后开始执行：**

```
📋 采集计划确认
- 监控关键词：codex, openclaw
- 启用数据源：Bing(2条), 搜狗(1条), Bilibili(3条)
- 邮件推送：zhangsan@example.com（或"不需要"）
- 采集后将进行 AI 智能分析筛选

正在开始采集...
```

---

## 步骤 7：执行数据采集

**7.1 安装依赖**

```bash
conda activate ai-hotspot-monitor && pip install aiohttp beautifulsoup4 lxml tenacity aiosmtplib
```

**7.2 生成配置文件**

在 `/tmp/hotradar/` 下创建 `config.json`。只用用户原始关键词搜索，每个数据源只发 1 次请求。

```json
{
  "keywords": ["codex", "openclaw"],
  "sources": {
    "bing": {"enabled": true, "maxResults": 2},
    "sogou": {"enabled": true, "maxResults": 1},
    "bilibili": {"enabled": true, "maxResults": 3, "orderBy": "pubdate"},
    "twitter": {"enabled": true, "apiKey": "用户提供的Key", "maxResults": 8},
    "youtube": {"enabled": false, "apiKey": "", "maxResults": 0},
    "douyin": {"enabled": false, "cookie": "", "maxResults": 0}
  },
  "maxAgeHours": 168,
  "qualityFilter": {"minTitleLength": 5, "minContentLength": 20}
}
```

`maxResults` 就是用户在步骤 4 中设置的抓取数量，脚本内部有硬上限约束，超过会自动截断。

**7.3 运行采集脚本**

```bash
conda activate ai-hotspot-monitor && python <skill-path>/scripts/hotradar_fetch.py /tmp/hotradar/config.json /tmp/hotradar/raw_results.json
```

`<skill-path>` 是本 skill 所在目录的绝对路径。

**7.4 读取采集结果**

读取 `/tmp/hotradar/raw_results.json`。如果脚本执行失败，告知用户原因并建议检查网络或配置。

**凭据数据源失败处理：** 采集脚本运行时，如果某个凭据数据源（Twitter/YouTube/抖音）因 API Key 或 Cookie 无效导致请求失败，脚本会自动跳过该源并继续其他源。记录失败的数据源名称及失败原因，用于在步骤 9 中通知用户。

---

## 步骤 8：AI 分析与筛选

读取 `/tmp/hotradar/raw_results.json`，其中 `keywordResults` 字段按关键词分组存储了采集结果。**对每个关键词的结果分别进行 AI 分析**，分析时以该关键词作为相关性判断的基准。

你亲自对每条结果进行 6 维度分析：

1. **isReal** (bool) — 内容是否为真实有价值的信息（排除标题党、假新闻、营销软文）
2. **relevance** (0-100) — 与**该条结果所属关键词**的相关性：
   - 0-30：完全不相关
   - 30-50：间接相关（同领域但未提及关键词）
   - 50-65：有一定关联
   - 65-80：直接相关（明确讨论关键词）
   - 80-100：高度相关（深度分析关键词主题）
3. **relevanceReason** (str) — 一句话解释相关性评分理由
4. **keywordMentioned** (bool) — 内容是否直接提及了关键词（含常见的大小写、连字符、空格等变体写法）
5. **importance** (low/medium/high/urgent) — 重要程度
6. **summary** (str) — 一句话说明与关键词的关联，格式："此内容与【{关键词}】的关联：{具体说明}"

**三层过滤规则**（严格按序应用）：

1. `isReal == false` → 过滤掉
2. `relevance < 50` → 过滤掉
3. `keywordMentioned == false && relevance < 65` → 过滤掉

只有通过全部三层过滤的结果才保留。详细评分标准请阅读 `references/analysis_guide.md`。

---

## 步骤 9：展示结果

**无论用户是否选择邮件推送，都必须在对话中展示筛选后的热点结果。**

**按关键词分组展示**，每个关键词一组，组内按重要性排序（urgent > high > medium > low），同一重要程度内按 relevance 降序排列。

**单关键词输出格式：**

```markdown
## 热点采集结果 — codex

**采集时间**：{当前时间}
**数据源**：{启用的数据源列表}
**原始结果**：{总数} 条 → AI筛选后：{通过数} 条

---

### 高度重要

**1. {标题}**
- 来源：{source} | 相关性：{relevance}/100
- 摘要：{summary}
- 链接：{url}

### 中等重要

...

---

> 关键词"codex"共获取 {原始数} 条结果，筛选后保留 {通过数} 条高质量热点。

⚠️ **数据源异常**：Twitter 因 API Key 无效未能获取数据，已自动跳过。
```

**多关键词输出格式（按关键词依次展示）：**

```markdown
## 热点采集结果

**监控关键词**：codex, openclaw
**采集时间**：{当前时间}
**数据源**：{启用的数据源列表}

---

### 关键词：codex

**原始结果**：{总数} 条 → AI筛选后：{通过数} 条

#### 高度重要

**1. {标题}**
- 来源：{source} | 相关性：{relevance}/100
- 摘要：{summary}
- 链接：{url}

#### 中等重要

...

---

### 关键词：openclaw

**原始结果**：{总数} 条 → AI筛选后：{通过数} 条

#### 高度重要

...

---

> 本次采集共处理 2 个关键词，总计获取 {总原始数} 条结果，筛选后保留 {总通过数} 条高质量热点。

⚠️ **数据源异常**：Twitter 因 API Key 无效未能获取数据，已自动跳过。
```

---

## 步骤 10：邮件推送（如需要）

如果用户在步骤 5 中选择了邮件推送，创建 `/tmp/hotradar/email_config.json` 并运行邮件脚本。**此步骤在步骤 9 展示结果之后执行。**

**邮件配置文件格式：**

```json
{
  "toEmail": "用户提供的收件邮箱",
  "keyword": "用户原始关键词（逗号分隔）",
  "hotspots": [
    {
      "title": "...",
      "url": "...",
      "source": "...",
      "keyword": "此热点所属的关键词",
      "relevance": 85,
      "importance": "high",
      "summary": "..."
    }
  ]
}
```

hotspots 中每条结果包含 `keyword` 字段标识所属关键词，邮件内容也按关键词分组展示。

SMTP 发件配置已硬编码在邮件脚本中，用户只需提供收件邮箱。

```bash
conda activate ai-hotspot-monitor && python <skill-path>/scripts/hotradar_email.py /tmp/hotradar/email_config.json
```

**邮件发送失败处理：** 如果邮件脚本执行失败（如收件邮箱不存在、SMTP 拒绝等），告知用户"邮件推送失败，原因：{错误信息}，热点结果已在上方对话中展示"。不重试，不重新询问邮箱。

---

## 项目配置参数参考

| 参数 | 值 | 说明 |
|------|-----|------|
| 抓取数量上限 | twitter:20, youtube:20, bilibili:20, douyin:20, bing:10, sogou:10 | 用户设置不能超过此值 |
| 默认抓取数量 | twitter:8, youtube:8, bilibili:3, douyin:3, bing:2, sogou:1 | 用户未自定义时使用 |
| MAX_AGE_HOURS | 168 | 时间过滤范围（7天） |
| SOURCE_PRIORITY | twitter:1 > youtube:2 > bilibili:3 > douyin:4 > bing:5 > sogou:6 | 数据源优先级 |
| FILTER_RULES | isReal==true, relevance>=50, keywordMentioned==true OR relevance>=65 | 三层过滤规则 |
| QUALITY_FILTER | minTitleLength:5, minContentLength:20 | 质量过滤 |

---

## 错误处理

1. 脚本执行失败：检查 Python 环境、依赖安装、网络连接
2. 某数据源抓取失败：跳过该源，继续使用其他源结果，在结果展示中通知用户
3. 凭据数据源认证失败（API Key/Cookie 无效）：自动跳过该源，在结果展示中通知用户具体失败原因（如"Twitter 因 API Key 无效未能获取数据"），不重新询问凭据
4. 邮箱格式不合法：在步骤 5 输入时检测，告知用户"邮箱格式不正确，已跳过邮件推送"，视为不需要邮件推送
5. 邮件发送失败：告知用户失败原因，热点结果已在对话中展示，不重试、不重新询问邮箱
6. 所有源都失败：建议检查网络或数据源配置
7. 没有结果通过 AI 筛选：建议调整关键词或增加数据源
