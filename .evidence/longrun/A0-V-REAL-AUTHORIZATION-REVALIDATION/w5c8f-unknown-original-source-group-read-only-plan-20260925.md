# W5c8f unknown 原源组纯只读证据计划

## 上位、边界

承接 231、A0-V fail-closed、W5c8d/e 和 AOS-000667。W5c8d 已可只读核原 attempt 双 Receipt；W5c8e 发现完整源组/Host 事务围栏仍缺。本波只为**持久 `unknown` 原 attempt**构造保存源组的纯只读证据，与双 Receipt 交叉核原 Requirement/Run/Case/Occurrence、actor/cutoff 和十二成员 manifest；不改变 Outbox/SQL/真实库，不接自动 Worker，不涉及过期 `claimed`。

## 文件级清单

- 复用 `services/aos-api/aos_api/ecommerce_analysis_data_requirement_route.py::AnalysisDataRequirementRouteReader.read_unknown` 与 `pipeline_snapshot_group_locator.py` 的原始记录验证，要求传入精确 `PipelineSourceClaimOwner` 和 `connect_read_only`。先证明这些依赖在整条路径上仅作 SELECT；若有任何隐式写入，停在审计，不包装。
- 新增 `services/aos-api/aos_api/ecommerce_analysis_unknown_source_group_evidence.py`：输入原 scope/claim、精确 claims、只读连接；先用 W5c8d resolver 找双 Receipt，再用原路由读取核保存组，输出仅诊断的源组证据。输出必须绑定同一 Requirement/Run/Occurrence，且不得返回可写命令或授权位；不同步读取商城源行。
- 新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c8f_unknown_source_group_evidence_pg.py`：一次性隔离 PG 原链证明正例、错误 tenant/attempt/Run/组、missing/ambiguous 成员、读事务约束与 source 调用计数不增加。测试可能复用 W5c8d 已证明的双 Receipt PG fixture；未覆盖负例如实登记。
- 仅新增本目录 verification；不改 Worker 和真实服务。若原路由依赖当前 head 导致合法原 attempt 不能读，先停并另立不依赖当前 head 的只读历史路由方案。

## 九步

1. 复习 231/产品、W5c8e 审计、authority/Git/真实 gate。
2. 方案先提交，固定仅 `unknown`、只读及原源组交叉绑定。
3. 审计旧路由路径无写；最小实现证据层，失败冻结。
4. 隔离 PG 正负例，source/coordinator 不重跑。
5. 近期短累计回归，不把 fixture 当真实运行。
6. 内置浏览器只读 rev4 停用验收，不冲刷队列。
7. 方案/代码/SQL/租户与时序复审，缺 Host 围栏不提升对账 authority。
8. verification 提交、AOS CAS/Prime 回读和真实 gate 复核。
9. 自动进入 W5c8g：单事务 Host-fenced `unknown` 对账先设计与隔离 PG 负例；过期 `claimed` 另立状态迁移，真实门不全不部署。

m1 单写不 push、不动其他分支；230 L0 挂起、商城源行不读、dev-org 仅零 canary、旧 attempt 不重发/不手工 `run_definition`。
