# W5c8h｜原 unknown attempt 同事务对账授权设计审计计划

## 上位与现场

承接 231-5/6、A0-V fail-closed、W5c8d/e/f/g、AOS-000669。W5c8g 只有同一**只读**快照的双 Receipt/源组诊断；`a0v_050` 的写函数只核原 tuple/双 Receipt，`a0v_094` Host fence 未进入该写事务。原 Worker 的 `_run_claim(reconcile=True)` 会调用 Coordinator，绝非零源只读对账。过期 `claimed` 单列，不混入 `unknown`。

2026-09-26 重启后 `colima aos-extension` 为 stopped，真实组合门 `FROZEN_REAL_CLOSURE_GATE_COMPOSITION / OBSERVATION_FirstInstallBlocked`，下钻为 `DATABASE_CONTAINER_UNAVAILABLE`。不在未知容器自启策略下拉起整套真实环境；上一波的 12 Run/0 closure Receipt 是**历史快照**，本波不得当作当前读回。

## 文件级清单与产出

- 只读审计 `services/aos-api/alembic/versions/a0v_050_data_requirement_outbox_completion.py`、`a0v_093/094`、`a0v_045`、`a0v_095`：固定当前授权谓词、可绕过入口、表不可变性与锁序。
- 只读审计 `services/aos-api/aos_api/{data_requirement_outbox_store.py,ecommerce_analysis_data_requirement_worker.py,ecommerce_analysis_unknown_source_group_evidence.py,pipeline_snapshot_group_locator.py}`：界定诊断快照与写事务的时间缝、原 `claimed` 差异、Worker 禁止自动对账的边界。
- 新增本目录 `w5c8h-host-fenced-unknown-reconciliation-authority-audit-20260926.md` 和 verification；更新 D-waves、AOS 上下文/Prime。**本波不修改生产代码、SQL 迁移、真实数据库、Worker/Host 配置**，不调用 `reconcile_completed`。
- 下一波文件级候选（仅规划，不在本波执行）：`a0v_096` 或其后迁移的默认关闭受控入口；`DataRequirementOutboxStore` 的显式 opt-in 写事务适配；隔离 PG 正/负例。若发现旧 `a0v_050` 仍可绕过新入口，先设计撤权/兼容切换，不得把新 guard 当成全局 authority。

## 九步与退出

1. 复习上位方案、W5c8g 证据、Git/authority、重启后真实 gate，只读定位观测冻结原因。
2. 本计划先提交，冻结为设计审计波；不借不可用真实环境扩大动作。
3. 逐层追踪旧 `a0v_050`、`a0v_094`、源组/Origin/Occurrence 的 SQL 关系，列出同一写事务必核谓词与 lock order。
4. 对比 Worker/Store 调用图与权限，验证新入口若只加在 Python 是否可被旧 SECURITY DEFINER 函数绕过。
5. 跑不触真实库/商城源的定向静态或纯单元检查；隔离 PG 因 Colima 停止不可运行则明确记为未验证，不造 GREEN。
6. 浏览器仅在可读服务恢复且不触启动旧 Host/Worker 时只读验收；否则记不可用，不把旧屏幕当新证据。
7. 方案/代码一致性复审，形成 SQL/权限/锁序/负例施工合同；任何条件无法证明则停在设计门。
8. audit + verification 落盘提交，AOS CAS/Prime/上下文回读；真实 gate 仍默认 frozen/no authority。
9. 自动进入 W5c8i：先方案后做隔离 PG 的同事务 Host-fenced `unknown` 对账拒绝/成功原型；**不接生产 Worker、不迁移真实库**。若当前容器恢复会自启真实 Host，先审计启动策略再启动；不能借本波设计直接发起真实对账。

m1 单写不 push、不动其他分支；230 L0 挂起、商城源不读、`dev-org/dev-project` 仅零 canary；未知结果不重发、不手工 `run_definition`。
