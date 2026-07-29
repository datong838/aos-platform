# W2 Worker W2 · A5 完成报告

## 状态

已完成（`feature/223-worker-2`）

## 目标对照

| 验收项 | 结果 |
|--------|------|
| Trace/指标至少接一条真实或采样 API | ✅ `GET /v1/aip/observability/summary` + `/traces` |
| 失败可降级并标演示路径 | ✅ `dataMode=demo` + `.obs-source-banner--demo` |
| 不改 `main.py` | ✅ 扩展已挂载的 `metrics.router` |
| Overview/Traces 优先走 API | ✅ |

## Commit

见 git log：`w2(A5): ...`

## 变更文件

- `W2_A5_PLAN.md` — 方案
- `services/aos-api/aos_api/aip_observability.py` — 从 metrics 采样拼装
- `services/aos-api/aos_api/routers/metrics.py` — 追加 2 个 endpoint
- `services/aos-api/tests/test_aip_observability.py` — 后端测（需 PG）
- `apps/web/src/pages/s2/ObservabilityPage.tsx` — Overview/Traces 接 API
- `apps/web/src/pages/s2/ObservabilityPage.test.ts` — 映射纯函数测
- `apps/web/src/styles.css` — 末尾 `/* === W2-A5 === */`

## 自测

| 项 | 结果 |
|----|------|
| vitest `ObservabilityPage.test.ts` | ✅ 41 passed |
| `build_summary` / `build_traces` 直测 | ✅ |
| pytest `test_aip_observability.py`（TestClient） | ⚠️ 本机 Docker/PG:5433 未起；import `aos_api` 需 PG。fixture 在 PG 可用时会跑通 |

## 风险

- 冷启动 KPI 可为 0（仍标真实 API / sampled）
- Traces 瀑布图仍用 `MOCK_SPANS`（本波未接 span 详情）
- Alerts / Metrics / Dashboards Tab 仍 MOCK

## 回滚

删除上述新增 endpoint + 前端 fetch/横幅即可恢复全 MOCK。
