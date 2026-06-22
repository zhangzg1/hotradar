# HotRadar - AI 热点监控与采集 Skill

HotRadar 是一个用于 AI 编程助手（Claude Code、Codex 等）的 Skill，帮你从多个数据源并行采集热点信息，经 AI 智能分析筛选后输出高质量结果。只需用自然语言描述你想关注的话题，HotRadar 会自动完成采集、分析、筛选全流程。

## 安装

### 放置 Skill 文件

将 `hotradar` 文件夹复制到对应工具的 skill 目录下：

**Claude Code：**

| 级别 | 路径 | 效果 |
|------|------|------|
| 项目级 | `<项目根目录>/.claude/skills/hotradar/` | 仅当前项目生效 |
| 全局级 | `~/.claude/skills/hotradar/` | 所有项目生效 |

**Codex：**

| 级别 | 路径 | 效果 |
|------|------|------|
| 项目级 | `<项目根目录>/.agents/skills/hotradar/` | 仅当前项目生效 |
| 用户级 | `~/.agents/skills/hotradar/` | 所有项目生效 |

目录结构应如下：

```
hotradar/
├── SKILL.md                 # Skill 定义（触发条件、执行流程）
├── README.md                # 本文件
├── requirements.txt         # Python 依赖
├── scripts/
│   ├── hotradar_fetch.py    # 数据采集脚本
│   └── hotradar_email.py    # 邮件推送脚本
└── references/
    └── analysis_guide.md    # AI 分析评分指南
```

### 配置运行环境

Skill 依赖 Python 3.10+ 及若干第三方库，需要提前准备好环境：

```bash
# 使用 Conda（推荐）
conda create -n ai-hotspot-monitor python=3.12 -y
conda activate ai-hotspot-monitor
pip install -r requirements.txt

# 或使用 venv
python -m venv ai-hotspot-monitor
source ai-hotspot-monitor/bin/activate   # Windows: ai-hotspot-monitor\Scripts\activate
pip install -r requirements.txt
```

环境准备好后，Skill 即可正常使用。

## 怎么使用

在对话中用自然语言告诉 AI 你想关注什么，以下说法都会触发 HotRadar：

- 「帮我追踪 Claude 的最新动态」
- 「搜集 GPT 相关的新闻」
- 「最近 AI 领域有什么热门话题」
- 「帮我监控 OpenAI 和 Anthropic 的热点」

**在 Claude Code 中**，你也可以输入 `/hotradar` 来直接调用。

**在 Codex 中**，你也可以输入 `$hotradar` 或 `/skills` 来直接调用。

触发后，HotRadar 会逐步引导你配置：

1. **关键词** — 你想追踪什么话题（支持多个）
2. **数据源** — 从哪里采集信息
3. **抓取数量** — 每个数据源抓多少条
4. **邮件推送** — 是否把结果发到你的邮箱

确认后自动执行采集和 AI 分析。

## 你会得到什么

采集完成后，你会看到按关键词分组的热点报告，每组结果包含：

- **标题与链接** — 一眼定位原文
- **来源标注** — 来自哪个数据源
- **相关性评分** — 与你关注的关键词有多相关（0-100）
- **重要性等级** — urgent / high / medium / low，帮你判断优先关注什么
- **一句话摘要** — 说明这条结果与关键词的具体关联

示例输出：

```
### 关键词：Claude

#### 高度重要

**1. Anthropic 发布 Claude 4.7：多项能力大幅提升**
- 来源：Bing | 相关性：92/100
- 摘要：此内容与【Claude】的关联：报道了 Anthropic 最新发布的 Claude 4.7 模型的性能提升
- 链接：https://...

#### 中等重要

**2. Claude 在代码生成场景下的使用经验总结**
- 来源：Bilibili | 相关性：75/100
- 摘要：此内容与【Claude】的关联：分享了 Claude 在编程辅助场景的实测对比
- 链接：https://...
```

## 数据源

| 数据源 | 类型 | 需要凭据 | 说明 |
|--------|------|:--------:|------|
| Bing | 网页搜索 | 否 | 开箱即用 |
| 搜狗 | 网页搜索 | 否 | 开箱即用 |
| Bilibili | 视频搜索 | 否 | 开箱即用 |
| Twitter | 社交媒体 | 是 | 需提供 [twitterapi.io](https://twitterapi.io) 的 API Key |
| YouTube | 视频搜索 | 是 | 需提供 [Google Cloud Console](https://console.cloud.google.com) 的 API Key |
| 抖音 | 短视频 | 是 | 需提供抖音网页版登录 Cookie |

免费数据源无需任何配置即可使用。凭据数据源在采集时会引导你输入，如果凭据无效会自动跳过并通知你。

## 配置参数参考

| 参数 | 值 | 说明 |
|------|-----|------|
| 抓取数量上限 | Twitter/YouTube/Bilibili/抖音: 20, Bing/搜狗: 10 | 用户设置不能超过此值 |
| 默认抓取数量 | Twitter/YouTube: 8, Bilibili/抖音: 3, Bing: 2, 搜狗: 1 | 用户未自定义时使用 |
| 时间过滤范围 | 168 小时（7 天） | 超过此时间的结果会被过滤 |
| AI 过滤规则 | 真实性 + 相关性 ≥ 50 + (提及关键词 OR 相关性 ≥ 65) | 三层过滤，全部通过才保留 |
