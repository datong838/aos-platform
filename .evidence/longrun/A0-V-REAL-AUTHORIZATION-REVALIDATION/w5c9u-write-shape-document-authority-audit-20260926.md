# W5c9u｜剩余写路由/参数形状文档权威只读审计

方案 `m1@62ce6fc1`。静态复核 FastAPI 当前 `iter_route_contexts` 和源 decorator，隔离短命进程不进入 lifespan/端口/DB/源，仅输出有效 route 的 path/method/模块、`include_in_schema` 与 OpenAPI tags。没有 GET/POST/PUT handler 调用。此前 W5c9m 首 FULL 匹配基线已确认十组 exact 的先者优先；本波不通过 schema 推断实际业务执行。

### 三组 exact POST

| 方法/路径 | 先注册可匹配 | 后注册 | 当前文档 |
| --- | --- | --- | --- |
| POST `/v1/ontology/branches` | `ontology.create_branch` | `phase4_ontology_branches.create_branch` | 两项均 included，OpenAPI 同键呈后置 `ontology-branches` 标签 |
| POST `/v1/pipelines` | `wave_ext.create_pipeline` | `phase5_pipelines.create_pipeline` | 两项均 included，同键呈后置 `phase5-pipelines` 标签 |
| POST `/v1/schedules` | `wave_ext.create_schedule` | `phase5_schedules.create_schedule` | 两项均 included，同键呈后置 `phase5-schedules` 标签 |

因此当前文档对三个 POST 都可能描述**不可达**的后置 handler，且 OpenAPI duplicate operation ID 仍有警告。只设后置 `include_in_schema=False` 不改真实 route 匹配；但写方法须在下一波用 endpoint-free 负例锁住：先者在前、两 route 仍注册、后者不进 schema、前者文档结构准确、其它 POST 不丢失。绝不通过调序、删除前者或手工调用 POST 来“验证”。

### 七组参数形状

共七组，不与 exact 10 相加为 endpoint 数：AIP lineage GET、Ontology object-types detail GET/PUT、Dataset detail GET、Schedules detail GET/runs GET/run POST。每组是不同模板变量名（例如 `{schedule_id}` vs `{sc_id}`）；OpenAPI 以不同字面键同时展示两套路径，只有 Dataset detail 的后置 `{ds_id}` 已在 W5c9n `included=false`，其余六组后置仍 included。它们不是 exact operation ID 重复，需按真实 matcher/参数约束另立负例，尤其 Schedules run POST、Ontology detail PUT。不能在 W5c9v exact POST 波里顺手隐藏。

结论：下一波 W5c9v 仅做三组 exact POST 文档权威的无执行修复方案→RED/GREEN，六组 shape 留后继波。18181 旧进程、8080 业务浏览器离线；原十二 Run row proof/Fleet/Owner/ACK/closure no-authority 不变。
