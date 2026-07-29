# W4 · W3 C6+C7 完成报告

> 分支：`feature/223-worker-4` · 基线 `b7c8760`  
> 方案：`W4_W3_C6C7_PLAN.md`

## 交付摘要

| 任务 | 目标% | 动作 | 结果 |
|------|-------|------|------|
| **C6 管道详情** | 55→70 | 视图 Tab 编辑/历史；历史接 `GET /v1/pipelines/:id/history`；变换节点配置+试运行 | ✅ |
| **C7 数据源详情** | 50→65 | Schema 树接 `/api/datasource/sources/:id/schemas…`；表预览优先连接器 preview；失败标演示路径 | ✅ |

## 改动文件

| 文件 | 说明 |
|------|------|
| `apps/web/src/pages/s2/pipelineCanvas.tsx` | C6 历史 Tab + 变换配置/试运行 |
| `apps/web/src/pages/s2/pipelineCanvas.test.ts` | 纯函数单测 ×12 |
| `apps/web/src/pages/s2/sourceDetailPage.tsx` | C7 Schema 树 + 搜索 + 连接器预览 |
| `apps/web/src/pages/s2/sourceDetailPage.test.ts` | 纯函数单测 ×9 |
| `services/aos-api/aos_api/routers/phase5_pipelines.py` | history/graph/config/trial demo fallback |
| `services/aos-api/aos_api/routers/phase6_schemas.py` | schemas/tables/columns/preview demo fallback |
| `apps/web/src/styles.css` | 末尾 `/* === W3-C6C7 === */` |
| `W4_W3_C6C7_PLAN.md` | 方案 |
| `W4_W3_DONE.md` | 本文件 |

**未改**：`main.py`、nav、Wiki/OT/Property/Function。

## 验收点

1. `/data/pipelines/:id` →「历史」Tab 见列表（API 或「演示路径」角标）
2. 选变换节点 → 改表达式 → 保存/试运行有反馈（API 或演示）
3. `/data/sources/:id` 探索 → Schema 树可折叠；搜索过滤表名
4. 选表 → 预览有列；失败/合成见「演示路径」
5. 单测：`pipelineCanvas*.test.ts` + `sourceDetailPage.test.ts` **42 passed**
6. 后端自测：未知 id → `demo:true`；真实 phase5 pipeline → `demo:false`

## 风险

- wave_ext 管道/源 ID ≠ phase5/phase6 → 多数 UI 会话走演示路径（已角标）
- router demo fallback 改变原 404 行为（仅 history/graph/config/trial/schemas 相关）

## 回滚

还原上表文件即可；无 DB migration；未 push。
