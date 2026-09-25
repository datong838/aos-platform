# W5c8g unknown 原源组无行锁历史读取计划

## 上位和安全边界

承接 231、A0-V fail-closed、W5c8d/e/f、AOS-000668。W5c8f 证明旧 `read_unknown` 路径的 `SELECT ... FOR SHARE` 在只读事务不可用。本波只提供**诊断专用**的无行锁历史源组读取；不修改旧业务路由默认锁/当前 head 检查，不写 Outbox、不调用 coordinator/source、不授予 `reconcile_completed`。真实旧链仍 12 原 Run running、关闭门未授权；230 L0 挂起、商城源行不读。

## 文件级清单

- 最小修改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py::AnalysisAdvanceHostService._accepted_occurrence_reference`：将原 `FOR SHARE OF o,a` 保持为默认；仅内部显式 `read_only=True` 时改用完全相同过滤/字段的无锁 SELECT，复用**同一**后续 Receipt 校验，不复制权威哈希算法。参数类型严格 bool，默认旧路径不变。
- 最小修改 `services/aos-api/aos_api/ecommerce_analysis_data_requirement_route.py`：新增只读 `read_unknown_historical`，只接受 `unknown` 原 attempt，在已注入 `connect_read_only` 的事务里走无锁 occurrence 证据、原精确 Requirement、原 PREPARING Receipt、ProductEventOrigin 和 `PipelineSnapshotGroupLocator`；不要求当前 head/可行动状态，但必须明确输出“历史诊断”，不得替代现有 `read_unknown` 的可执行路由。若现有返回类型易混淆，则新增专用 evidence 类型。
- 新增 `services/aos-api/aos_api/ecommerce_analysis_unknown_source_group_evidence.py`：组合 W5c8d 双 Receipt 与无锁历史源组，要求同原 Requirement/Run/Case/Occurrence、唯一成员绑定和 cutoff；仅返回证据，无授权布尔、无可执行 route。
- 新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c8g_unknown_source_group_read_only_pg.py`：原链隔离 PG 正例，以及读事务/错误 tenant、attempt、occurrence、源 Run、组成员/manifest、多组、head 后移等负例；断言源调用计数不增加、旧默认 `FOR SHARE` 路径仍保持。若测试 fixture 缺适用造数，如实登记未覆盖，不删门。
- 本目录 verification、D-waves/上下文更新；真实库不迁移，8080 不重启，Worker 不接线。

## 九步

1. 复习 231/产品、W5c8f 停止证据、现有读/锁代码、authority/Git/真实 gate。
2. 本方案先提交，固定旧默认锁与新诊断无锁分流。
3. 先写失败的隔离 PG 断言，再实现最小无锁读取和双证据绑定。
4. 专项隔离 PG 正负例；遇任何隐式写/不唯一即停。
5. 近期短累计及旧 Coordinator 回归，确认默认路径不退化。
6. 内置浏览器只读 rev4 停用，不冲刷队列。
7. 方案/代码/SQL/源组与 Host 时序复审，诊断证据不解释为对账 authority。
8. verification 提交、AOS CAS/Prime 回读、真实 gate 复核。
9. 自动进入 W5c8h：先方案评估同事务 Host fence + 源组/双 Receipt 谓词的受控 `unknown` 对账，过期 `claimed` 仍另立状态迁移门。

m1 单写不 push、不动其他分支；dev-org 仅零 canary，旧 attempt 不重发/不手工 `run_definition`。
