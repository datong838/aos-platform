# W5c9l｜有效路由十组碰撞精确审计

方案 `m1@97863007`。一次 90 秒上限、无 lifespan/端口/源/DB 的短命进程，以 `fastapi.routing.iter_route_contexts(app.routes)` 展开当前依赖库 `_IncludedRouter`，按有效 method/path 和有效 `unique_id` 聚合；只输出方法/路径/端点模块，不输出 schema/请求体/凭据。

总量：有效 method 路由 4,515；**同 method/path 碰撞 10 组、Operation ID 碰撞 10 组**，每组各两个注册项。顺序如下，左侧先注册、右侧后注册：

| 方法/路径 | 先注册 endpoint | 后注册 endpoint |
| --- | --- | --- |
| GET `/v1/builds` | `wave_ext.list_builds` | `builds.list_builds` |
| GET `/v1/datasets` | `wave_ext.list_datasets` | `phase5_datasets.list_datasets` |
| GET `/v1/ontology/branches` | `ontology.list_branches` | `phase4_ontology_branches.list_branches` |
| GET `/v1/ontology/graph-health` | `ontology.graph_health` | `phase4_ontology_branches.graph_health` |
| GET `/v1/ontology/object-types` | `ontology.list_object_types` | `phase4_ontology_types.list_object_types` |
| GET `/v1/pipelines` | `wave_ext.list_pipelines` | `phase5_pipelines.list_pipelines` |
| GET `/v1/schedules` | `wave_ext.list_schedules` | `phase5_schedules.list_schedules` |
| POST `/v1/ontology/branches` | `ontology.create_branch` | `phase4_ontology_branches.create_branch` |
| POST `/v1/pipelines` | `wave_ext.create_pipeline` | `phase5_pipelines.create_pipeline` |
| POST `/v1/schedules` | `wave_ext.create_schedule` | `phase5_schedules.create_schedule` |

这十组可确证 OpenAPI `operationId` 不唯一以及路由表 method/path 不唯一；实际运行时谁先响应需按 Starlette/FastAPI 匹配规则和具体依赖作独立测试，不能仅凭静态顺序把后项宣称可用。`phase5_datasets.py` 自注释早已标记两个 GET 为 `NOT_REACHABLE_DUPLICATE`；本审计精确同 path 碰撞只找到列表 GET，不把 `/{id}` 与 `/{ds_id}` 的参数名差异漏诊或强行计入十组。它是另一种**路径形状**遮蔽风险，需后续独立审计。

本波不改路由注册/顺序/Operation ID/文档，不能为消警告而意外启用原先未达的写端点。W5c9m 先文件级方案，对十组及参数路径形状作兼容风险基线，优先设计保持运行时分派不变的文档单一权威与负例测试。原 A0-V 真实 ACK/closure no-authority 不变。
