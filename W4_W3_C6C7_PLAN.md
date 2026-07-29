# W4 · W3 C6+C7 方案（管道详情 55→70 · 数据源详情 50→65）

> 分支：`feature/223-worker-4` · 基线 `b7c8760`  
> 依据：`227-未完成项补齐计划.md` W3·C6+C7；参考 `223-deep-checklist-3` 页8/9  
> 原则：最小改动；不做全像素翻修；不碰 Wiki/OT/Property/Function/nav/main

## 1. 验收对照

| 任务 | 目标 | 本波动作 |
|------|------|----------|
| **C6 管道详情** | 变换节点 **或** 运行历史至少一侧可用 | **两侧都做轻量接线**：视图 Tab「编辑/历史」+ 历史列表；变换检查器可编辑表达式并试运行 |
| **C7 数据源详情** | Schema 树或表预览与连接器一致 | 左栏 Schema 树（schema→表→列）；预览优先连接器 schema preview；失败标演示路径 |

## 2. C6 · pipelineCanvas

### 2.1 已有 API（优先）

- `GET /v1/pipelines/:id/history`（phase5）
- `GET /v1/pipelines/:id/graph`
- `GET/PUT /v1/pipelines/:id/nodes/:nodeId/config`
- `POST /v1/pipelines/:id/nodes/:nodeId/trial-run`

列表页仍用 wave_ext `GET /v1/pipelines`（`items` 含 sourceId/datasetRid）。phase5 ID 空间不同 → **404/失败时前端合成演示历史**，角标「演示路径」。

### 2.2 UI 增量（最小）

1. 顶栏下增加视图 Tab：`编辑` | `历史`
2. **历史**：拉 history API；成功展示 action/actor/detail/时间；失败 → `buildDemoHistory(pipe)` + 演示角标
3. **变换节点**：选中 transform 时展示可编辑「表达式 / 过滤条件」；「保存配置」优先 PUT node config（需 graph 解析到 transform 节点），失败写 localStorage；「试运行」优先 trial-run，失败标演示
4. 不重做 DAG 全拓扑 / 不翻修视觉

### 2.3 纯函数（可测）

- `buildDemoHistory(pipe)` / `formatHistoryTime(ts)` / `historyPathLabel(path)`
- `pickTransformNode(graph)` / `xformStorageKey(pipelineId)`
- `load/saveLocalXform` / `formatTrialMsg`

## 3. C7 · sourceDetailPage

### 3.1 已有 API（优先）

- `GET /api/datasource/sources/:id/schemas`
- `GET .../schemas/:name/tables`
- `GET .../tables/:table/columns`
- `POST /api/datasource/sources/:id/preview`

wave_ext `/v1/sources` ID ≠ phase6 source ID → 多数情况走演示。  
**策略**：先打 phase6 schemas；失败则按连接器类型用 `demoSchemaTree(connectorType)`，角标「演示路径」；采样预览保留现有 analytics 路径作为补充。

### 3.2 UI 增量（最小）

1. 左栏改为可折叠 Schema 树（schema → 表 → 列名+类型+PK）
2. 搜索框接线过滤表名
3. 选中表后：优先 phase6 preview；失败保留原 datasets/objects 采样；再失败演示行
4. 右栏增加「当前表列」摘要（类型/PK），不改动凭证/同步 Tab 主流程

### 3.3 纯函数（可测）

- `demoSchemaTree(type)` / `filterSchemaTree(tree, q)` / `flattenTables(tree)`
- `schemaPathLabel(path)` / `formatColumnBadge(col)`

## 4. 后端（可选最小）

| 文件 | 改动 |
|------|------|
| `phase5_pipelines.py` | history/graph：pipeline 不存在时返回 `demo:true` 合成数据（避免 UI 全 404）；**不改** list 路由 |
| `phase6_schemas.py` | schemas：source 不存在时返回 `demo:true` 默认 public 树（与连接器无关的通用演示）；**不改** main |

若引擎测试依赖 404，仅在 router 层 fallback，引擎行为不变。

## 5. 文件边界

| 文件 | 改动 |
|------|------|
| `apps/web/src/pages/s2/pipelineCanvas.tsx` | C6 |
| `apps/web/src/pages/s2/pipelineCanvasPhase7.test.ts` 或新建 `pipelineCanvas.test.ts` | 纯函数测 |
| `apps/web/src/pages/s2/sourceDetailPage.tsx` | C7 |
| `apps/web/src/pages/s2/sourceDetailPage.test.ts` | 新建 |
| `services/aos-api/aos_api/routers/phase5_pipelines.py` | history/graph demo fallback |
| `services/aos-api/aos_api/routers/phase6_schemas.py` | schemas demo fallback |
| `apps/web/src/styles.css` | 末尾 `/* === W3-C6C7 === */` |
| `W4_W3_C6C7_PLAN.md` / `W4_W3_DONE.md` | 方案与交付 |

**禁止**：Wiki*/ObjectType*/Property*/Function*/nav/main；push；改 m1；merge。

## 6. 风险与回滚

| 风险 | 缓解 |
|------|------|
| wave / phase5 ID 不一致 | 演示路径明确标注；不阻断页面 |
| phase6 schemas demo 掩盖真实 404 | 响应带 `demo:true`；UI 角标 |
| 改 router fallback 影响严格 404 调用方 | 仅 history/graph/schemas；引擎仍 KeyError |

回滚：还原上表文件即可。

## 7. 自测清单

1. `/data/pipelines/:id` → 切「历史」见列表（API 或演示）
2. 选变换节点 → 改表达式 → 保存 / 试运行有反馈
3. `/data/sources/:id` 探索 Tab → Schema 树可展开；搜索过滤
4. 选表 → 预览有列；失败见演示角标
5. vitest：pipeline + source 纯函数通过
