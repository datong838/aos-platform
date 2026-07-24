# 长期项目记忆 — AOS Platform / Palantir Foundry 对标项目

## 用户信息
- **称呼**：大同
- **Mac Word 兼容性**：python-docx 生成的 .docx 在 Mac 版 Word 中图片不显示，使用 WPS Office for Mac 查看

## 项目概述

基于 Palantir Foundry 产品文档，自研 AOS（AI Ontology System）平台。核心工作流：Foundry 文档 → Word PRD → 差距分析 → 开发计划 → 代码实现 → HTML Demo。

### 关键路径
- **代码库**：`/Users/ddt/work/projects/ai_agent/aos-platform`
- **产品方案**：`/Users/ddt/work/projects/ai_agent/docs/palantier/20_tech/`
- **Word PRD 输出**：`/Users/ddt/work/projects/ai_agent/docs/palantier/prddetail/`
- **HTML Demo**：`/Users/ddt/work/projects/ai_agent/docs/palantier/foundry/html/`
- **页面↔截图映射表**：`/Users/ddt/work/projects/ai_agent/docs/palantier/prddetail/PAGE_SCREENSHOT_MAP.md`

## 三大核心文档

| 文档 | 路径 | 状态 |
|------|------|------|
| **220w 差距对照分析** | `20_tech/220w-与目标系统差距对照分析.md` | v1.17 ✅ 52/52 专题完成 |
| **220plan 开发计划** | `20_tech/220plan-分阶段开发与里程碑计划.md` | v1.2 ✅ 261 项进度看板 |
| **页面↔截图映射表** | `prddetail/PAGE_SCREENSHOT_MAP.md` | 56 页全量映射，56/56 ✅ |

## 电商平台接入方案（8 平台 P0+P1+P2 全完成）

```
微商城（JDBC·⭐）→ 淘宝/天猫（REST·HMAC·⭐⭐）→ 拼多多（REST·MD5·⭐⭐）
  → 京东（REST·HMAC·POP/自营·⭐⭐⭐）→ 抖音（REST·内容+电商·⭐⭐⭐⭐）
  → Shopify（GraphQL·Webhook·⭐⭐⭐）→ Amazon（SP-API·AWS4·多区域·⭐⭐⭐⭐⭐）
```

- 微商城：v2.0 完整可用作模板（302 张表、341 个 API）
- 淘宝+天猫：P0/P1 完成（字段级对照，合并方案）
- 拼多多：P0 v1.0 + P1 API清单(32接口) ✅
- 京东：P0 v1.0 + P1 API清单(42接口) + POP/自营差异分析 ✅
- 抖音：P0 v1.0 + P1 API清单(42接口) + 达人佣金模型 + 抖店云部署 ✅
- Shopify：P0 v1.0 + P1 GraphQL Schema(18Q+7M+13Webhook) ✅
- Amazon：P0 v1.0 + P1 SP-API清单(40接口) ✅
- 天猫、跨境 Shopify：指向文档（主方案已覆盖）
- **P2 连接性文档（4篇）**：跨平台Ontology统一模型 + 核心实体字段级对照矩阵 + Connector架构设计(G1-G10全覆盖) + 实施排期与里程碑(12周甘特图)
- **000 总方案**：`000-电商平台接入总方案.md` v2.0（6 阶段端到端链路 × 56 页界面对照，~510 行）
- **跨平台总览**：`电商平台接入总览.md` v2.0
- 文档总计：**23 篇**
- **所有平台 P2 统一阻塞于**：REST API Connector（W2+ G1）+ OAuth Token Manager（W2+ G2）

## 220plan 开发进度

### W1 Phase 0-6：✅ 全部完成（24 项）
### W2+ 高优先级（27 项，已完成 6 项）
- ✅ Dynamic Scheduling / Data Connection 增量同步 / Pipeline Builder 变换系统增强 / Data Connection 事务类型 / AIP Logic 无代码编辑器 / Pipeline 多数据源
- ⬜ 剩余 10 项：媒体集(2) / Data Lineage L1 / 甘特图 / OE 图表 / Object Views / Action(3) / Web IDE
- **220plan 实际已完成 270 项**（全部 ✅）

### 220plan2 第二批开发计划（v3.1 · 316 项）
- 文件：`20_tech/220plan2-分阶段开发与里程碑计划（第二批）.md` **v3.1**
- 220w 原始 937 🔴 → v2.0 初步去重 837 → v3.0 与 220plan 去重 320 → v3.1 与 221plan 去重 **316 项**
- v3.0 移除 517 项（已被 220plan 覆盖为主）+ v3.1 移除 4 项（[LL]×3+[EV]×1 被 221plan 覆盖）
- P0/W3(23项) / P1/W4(123项) / P2/W5(123项) / P3/W6(47项)
- [LL] k-LLM 路由 和 [EV] Evals/Decision 模块已移交 221plan（AIP 决策引擎）

### 220plan2 编码进度
- **W3 ✅ 完成**（23项/69文件/218测试PASS）— commit `5c70557`
- **W4 ✅ 完成**（123项/369文件/5627回归PASS）— commit `edfa0de`，269 routes
- **W5 ✅ 完成**（123项/369文件/1107测试PASS）— commit `697fce8`，392 routes
- ⬜ W6 待编码（47项）
- 编码模式：Engine(Pydantic+Singleton+threading.Lock) + Router(FastAPI APIRouter) + Test(pytest 9用例)
- worktree：`aos-platform-220plan2/` → feature/220plan2
- main.py include_router 用 `application.include_router()` 模式
- 前端路由通过 nav.ts (status="s2") + BlueprintStubPage 自动加载 foundry/html

### 221plan AIP 决策引擎（v1.0 · ~35 任务）
- 文件：`20_tech/221plan-分阶段开发与里程碑计划.md` v1.0
- 3 Phase：基础增强 → 生产安全 → 能力扩展
- 覆盖：LangGraph/ProposeEdits/Wiki字段/Logic版本管理/Evals门控/跨模型对比/L4熔断/可观测性/Model Catalog/AIP Assist/Analyst/DocIntel
- 参考文档：221m 差距对照分析

## HTML Demo 演示站（56/56 全量完成 ✅）

- 56 个页面，路径 `foundry/html/` — 全部完成
- 设计系统：demo.css（Palantir 浅色主题），累计 ~7000+ 行
- 全局布局：深色 48px 图标导航栏 + 白色 260px 上下文侧栏 + 白色 48px 顶栏 + 浅灰内容区(#F0F2F5)
- 三大优先级：高 28 页 ✅ + 中 12 页 ✅ + 低 15 页 ✅ = 56 页
- **导航完整性验证**：56 页零孤岛，每个页面均通过侧边栏菜单或内容区链接可达
- 侧边栏 6 大分区：工作台(9) / AIP(10) / 本体(7) / 数据集成(13) / Apollo(7) + 概览(1)
- 侧边栏折叠修复：用 `display: none` 替代 `max-height: 0` 方案
- okf-funnel.html 已从重定向页改造为 OKF 行业漏斗概览页
- HTTP 服务器端口 8765

## Word 文档生成

- **技能已安装**：`~/.workbuddy/skills/palantir-topic-docx/`
- **脚本**：`generate_topic.py`（706 行）
- **用法**：`python generate_topic.py <专题目录> [--output-dir <输出目录>]`
- **运行环境**：`/Users/ddt/.workbuddy/binaries/python/envs/default/bin/python`（需 python-docx + Pillow）
- 52/52 专题全部完成，共 1175+ 篇文档、1000+ 张图片嵌入

## engineering-process 技能

- 已将 Superpowers 方法论吸收为用户级编码技能
- 路径：`~/.workbuddy/skills/engineering-process/SKILL.md`
- 7 个工程阶段：Brainstorming → Planning → TDD → Debugging → Verification → Code Review → Parallel Solving
- 包含反模式速查表和决策路由图

## 开发原则（用户强调）
1. 每个功能点开发完立即写单元测试，全部通过才能下一步
2. 每个波次完成后做集成自测：重启系统 → 验证页面 → 验证风格
3. UI 功能设计对标 `foundry/html/` 中的 HTML 蓝图页（56 个参考文件）
4. 给出阶段顺序、里程碑和依赖关系
