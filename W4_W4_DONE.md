# W4 · E1+A8 完成报告

> 分支：`feature/223-worker-4` · 基线 `4a8ceb8`  
> 方案：`W4_W4_E1A8_PLAN.md`

## E1 决策（落地）

**`pipeline-doc-intel.html` → 并入文档智能 `/aip/doc-intelligence`，不新建侧栏菜单。**

| 动作 | 结果 |
|------|------|
| 说明条 | 「DocIntel 管道能力收敛于此页」 |
| 轻量管道条 | 输入→Use LLM→输出 + 6 模板 chip + 试运行 |
| 残留路由 | `/data/pipeline-doc-intel`、`/pipelines/doc-intel` → 重定向 |
| nav | **仅注释**；未新增菜单项 |

## A8 文档智能（35%→55%）

| 动作 | 结果 |
|------|------|
| 真 API 抽取 | `POST /api/aip/docintel-extract/run`（同 router，未改 main） |
| 流水线试运行 | `POST /v1/docintel/pipeline`（已有） |
| 失败回落 | 角标「演示路径」+ `demoExtractFields` MOCK |

## 改动文件

| 文件 | 说明 |
|------|------|
| `apps/web/src/pages/s2/DocumentIntelligencePage.tsx` | A8 接线 + E1 并入 UI |
| `apps/web/src/pages/s2/DocumentIntelligencePage.test.ts` | 纯函数测 +5 |
| `services/aos-api/aos_api/aip_docintel_extract.py` | `run_extract` |
| `services/aos-api/aos_api/aip_docintel_extract_router.py` | `POST /run` |
| `services/aos-api/tests/test_aip_docintel_extract.py` | run_extract 单测 |
| `apps/web/src/App.tsx` | 两条重定向（最小） |
| `apps/web/src/nav.ts` | 仅注释 |
| `apps/web/src/styles.css` | 末尾 `/* === W4-E1 === */` |
| `W4_W4_E1A8_PLAN.md` / `W4_W4_DONE.md` | 方案 + 本文件 |

**未改**：`main.py`、Link*/Action*/Capability*；未 push / 未改 m1。

## 验收点

1. `/aip/doc-intelligence` 见说明条「DocIntel 管道能力收敛于此页」
2. 「运行抽取」→ 真 API 成功标「真 API」；失败标「演示路径」+ MOCK 字段
3. 「管道试运行」→ `/v1/docintel/pipeline` 或演示提示
4. 访问 `/data/pipeline-doc-intel` 重定向到文档智能；侧栏无新菜单
5. 单测：`DocumentIntelligencePage.test.ts` **68 passed**
6. 后端：`run_extract` 自测 `demo:false` + 字段列表（本机无 DB 时用 importlib 隔离引擎）

## 风险

- `/run` 为启发式抽取，非真实 LLM；联调仍属真 HTTP 路径
- 页载自动试抽一次；API 不可用时静默回落演示（有状态文案）

## 回滚

还原上表文件即可；无 DB migration；未 push。

## 建议下一批 226 视觉对账页面

1. `/aip/doc-intelligence` ↔ `document-intelligence.html`
2. `/data/pipelines/:id` ↔ `pipeline.html`（管道详情）
3. `/data/sources/:id` ↔ 数据源详情视觉稿
4. `/data/lineage` ↔ `lineage.html`
5. `/aip/capabilities` ↔ `aip-capabilities.html`（智能体插件）
