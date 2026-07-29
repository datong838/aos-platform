# W2·A5 可观测脱 MOCK 方案（45%→60%）

## 目标

`ObservabilityPage` Overview / Traces 至少接一条真实或采样 API；失败可降级并标「演示路径」。

## 约束

- 不改 `main.py`（metrics router 已挂载）
- 不碰 Analyst / Capacity / ModelCatalog / Studio / Publish / nav.ts
- 最小改动；`styles.css` 仅末尾追加 `/* === W2-A5 === */`

## 后端

| 项 | 说明 |
|----|------|
| 新模块（可选） | `aos_api/aip_observability.py`：从 `metrics.snapshot()` 拼装 KPI/趋势/采样 traces |
| 路由 | 在已挂载的 `routers/metrics.py` 追加： |
| | `GET /v1/aip/observability/summary?range=` → `{ source, range, kpis, trend, totals }` |
| | `GET /v1/aip/observability/traces?limit=` → `{ source, items[] }` |
| 鉴权 | 与现有 `/v1/metrics` 一致：`require_principal` |
| 空数据 | 无采样时仍返回 `source: "sampled"` 与零值 KPI（非 404），前端可识别 live |

## 前端

| 项 | 说明 |
|----|------|
| 文件 | `ObservabilityPage.tsx` |
| 拉取 | mount / 手动刷新 / 自动刷新 tick → `apiGet` summary（及 traces） |
| Overview | KPI + sparkline 优先用 API |
| Traces | 列表优先用 API items；瀑布图仍用本地 MOCK_SPANS（本波不接 span 详情） |
| 降级 | catch → 保留 MOCK，`dataMode=demo`，顶部「演示路径」横幅 |
| live | `dataMode=api`，顶部「真实 API」横幅 |

## 样式

`styles.css` 末尾：`.obs-source-banner` / badge（与 Draft 演示路径语义一致，类名独立避免冲突）。

## 测试

- 后端：`test_aip_observability.py` — summary/traces 200 + 字段；无 auth 401
- 前端：纯函数映射 `mapSummaryToKpis` / `mapTraceItems` 单测

## 风险与回滚

- 风险：内存 metrics 冷启动 KPI 全 0（可接受，仍标真实 API）
- 回滚：删除新增 endpoint + 前端 fetch，恢复全 MOCK

## 验收

1. Overview 或 Traces 能走 `/v1/aip/observability/*`
2. API 失败时 MOCK + 演示路径可见
3. 不改 main.py；commit `w2(A5): ...`
