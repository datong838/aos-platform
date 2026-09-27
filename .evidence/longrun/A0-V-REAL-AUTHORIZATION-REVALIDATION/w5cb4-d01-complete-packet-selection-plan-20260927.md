# W5CB4 D01 完整来源包选择权威施工方案（2026-09-27）

## 上位约束与现有事实

- 231 A1-02/03 与 231-9 BG-02/03 要求自然 Occurrence/Case/Run→获批 exact 方案→真实 D01 分析；栖月汇产品方案要求有来源、角色和后续任务交接。当前 `NaturalD01AtomicCoordinator` 未注册 Host，只在同事务校原链与 Task SourceSelection；`NaturalD01Issuer` 已要求批准 Plan portrait `inputRefs` 与 packet/AgentRun 引用集合一致。
- `BusinessInvestigationCompilationReceipt` 没有 Method、Eval、Metric→Query→EvidenceBundle、DisclosureGrant、窗口、markings 与 cutoff 的完整关系。`PlanStep.inputRefs` 只有引用集合，不含 exact 哈希和关系；`aip_task.selection_ref` 是原数据源选择，不是 D01 包。各原 Owner 分立，现有 `PortraitGenerationCommand` 是调用者输入，不是选择授权。不可用“最新一行”或成功读取来倒推批准。
- 因此完整包需要一个明确、可撤销、同租户的批准选择；只保存 exact 引用和使用边界，不复制源材料。其审批不能由开发者手接线或合成 actor 代替，旧 Task/Run 不回填。

## 拟增文件与数据合同（先 RED，后最小实现）

1. `services/aos-api/aos_api/ecommerce_analyst_d01_source_selection.py`：定义 `D01SourceSelectionProposal`，绑定 exact TaskRun/Plan/原 `SourceSelectionRevision`、完整 `D01SourcePacket`、原 Plan hash、提案 actor 与稳定幂等 key。`packet` 须与批准 Plan 首步 `inputRefs` 精确一致；cutoff 须等于原 AnalysisRuntimeReceipt cutoff，且 query/bundle/window 不越界。提出者不能自批。
2. `services/aos-api/alembic/versions/a0v_107_ecommerce_d01_source_selection.py`：只加 append-only proposal、approval、revocation 和 idempotency Receipt；以 `(org_id,project_id)` 为前缀，RLS `FORCE`、原不可变触发器、Runtime 只需最小 `SELECT/INSERT`。同一 TaskRun/Plan 只允许一个批准选择；撤销后不能换同一 Run 的 packet，需新的正式 Plan/Run。迁移 `downgrade` 禁止删历史。迁移前先独立核当前数据库身份、备份与基线；本波只在隔离 PG 跑，不自动升级当前实例。
3. `services/aos-api/aos_api/ecommerce_analyst_d01_source_selection_store.py`：原事务 API `propose/approve/revoke/read_current`；每次校 scope、原 Plan 当前批准及内容 hash、原 TaskRun 和 SourceSelection identity、maker/checker 分离与权限。相同 key/相同 payload 幂等回原 Receipt，同 key/不同 payload 冲突；未知提交仅按原 key 只读对账，不造第二 ID。读取时再查撤销、原 Owner 当前来源/Grant 与有效期。
4. `services/aos-api/aos_api/ecommerce_analyst_d01_atomic.py`：只接受 `read_current` 返回的原批准选择，外部 packet 必须 bit-for-bit 等于选择，不从调用者任意 packet 生成授权；整个读取、原链校验和 AgentRun Owner 写处于同一 serializable 事务。仍不注册 Host/Provider。
5. `services/aos-api/tests/extension_runtime/test_ecommerce_analyst_d01_source_selection_pg.py` 与 `test_ecommerce_analyst_d01_atomic.py`：RED 覆盖零/多、跨租户、错 Plan/Run/原选择、错 cutoff、过期/撤销、Grant 缺失、maker=checker、重复 key 漂移、未知提交、并发双批准、原事务回滚与 `dev-org` 零 canary。隔离 PG 正例需有真正 proposal→独立 checker→批准→同事务选择→Owner Receipt 读回，不以 mock 代替真实库门。

## 执行顺序与退出

先定稿 schema/权限与完整负向测试，再实现 Owner、隔离 PG、累计回归；必要时浏览器只验产品选择/批准入口，不以 API 绿色代替。当前新库 `a0v_106` 不自动迁移，8080/8434 安全预览保持禁入，18181/Host/Provider 不开。完成必须落 verification、m1 精确 commit、AOS authority 经 CAS 和 Prime 回读；如原权限/当前备份不足，只阻断实例迁移，继续代码与 BG-00 主线。不得因 D01 包单点无限延迟首链其他配置。

施工先分可独立验收的最小切片：A. 候选提案合同（无批准权、无 DB/Host）；B. append-only Owner/schema 与 proposal/approval/revoke Receipt；C. 原事务选择读回及 D01 Atomic 接线；D. 当前实例迁移/产品入口（独立备份与真实权限前置）。A 的 GREEN 绝不关闭 B/C/D 或本方案总门。

### B 子波数据库安全细化（A 已于 `088fe0eb` 落盘）

- proposal 表以 `(org_id,project_id,selection_id)` 为主键，另有 `(org_id,project_id,task_run_id,plan_revision_id)` 与 proposal key 唯一约束；存 canonical 提案 JSONB、请求 hash、提案人、时点、内容 hash。FK 指向同租户 `aip_task_run`/`aip_plan_revision`。相同 Run/Plan 不允许第二个不同 packet，未知提交只能按原 key 查。
- approval 表同租户 FK proposal，`selection_id` 与 approval key 均唯一；checker 必须是当前 Plan 的 `approved_by` 且不同于 maker，批准时要求 Plan 仍是 Task 当前 approved 版本、Run 仍 running、Plan hash 和原 Task `selectionRef` 未漂移。revocation 表同租户 FK approval，`selection_id` 唯一，撤销不能覆盖历史批准。每阶段独立 Receipt/幂等哈希，直接重复原 key 原 payload 回原 Receipt、不同 payload 冲突。
- 三表 `ENABLE/FORCE RLS`、不可 UPDATE/DELETE/TRUNCATE、`aos_runtime` 只给 `SELECT`；唯一写路径是显式 `SECURITY DEFINER` 函数，其自身再核 serializable scoped 事务、原表和 actor。隔离 PG 先证实直写拒绝、无 scope/跨租户拒绝、同键漂移和并发不双批准。**不能仅靠 Python 检查而把底表 INSERT 放给共享 Runtime 角色。**
- 代码/迁移同时验证到可执行且当前库有独立备份后，才评估 a0v_106→107 的当前实例升级；在此之前安全预览保持已运行的 106 版本，绝不以测试库迁移冒充当前实例升级。

## 本波首先要裁决的设计风险

- `PlanStep.inputRefs` 没有 content hash；proposal 的 exact refs 由原各 Owner 校验，批准者需在界面看到关系/窗口/Grant 摘要而非仅看到集合。
- 旧 Plan 的 portrait `inputRefs` 为空，应拒绝而非补填；新的完整 Plan/Run 必须由正常业务流程产生。
- 所有新表是引用/决策权威，不是商城数据副本；不保存 Evidence 正文、凭据或 Provider 输入文本。
