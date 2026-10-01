# GT-b4 同账本预算与同物理 Provider 容量：文件级施工方案

基线：2026-10-02 03:16 CST，`aos-platform/m1 7eed628e`，AOS-001087。范围是用户已批准的 Model 首评用途代码与隔离验证；当前权威库只读 `a0v_118`，代码头 `a0v_133`，不迁移、不读取 Secret、不调用 Provider/Host。本文件先固定方案，再写 RED/代码。

## 上位合同与源码复核

- `docs/.../231-5-真实业务自动链调度审批费用与恢复实现方案.md:57-69`：任务/日/试点预算三桶同事务锁，`held+submitted+settled+unknown` 共用限额；先提交预算/调用意图，再发送；未知只读对账。
- BG00GT D-wave：首评不能造假 Task/AgentRun，不能让 Eval 池与业务池各享同一物理 Provider 全额；正式身份不足则禁发送。
- `aip_budget_reservation_contracts.py:ReserveBudgetRequest` 只收 `Task`；`derive_bucket_authorities` 的日/月账户基于 `BudgetRevision` ID。`aip_budget_reservation_store.py:reserve` 校验真实 Task 与绑定 Task 的 ApprovalEvent，先锁三桶再占额；模型 `BudgetPolicyRevision` 另含 `budgetRevisionRef`，可精确回到同一 BudgetRevision 账户。
- `aip_model_capacity_reservation.py:reserve` 仅锁 exact Route 池 head，按 `(pool_id,pool_revision)` 计数，要求 `agent_run_id`。`aip_model_capacity_authority.py:_require_dependencies` 要 Route/Model/Provider 都 active；尚未评测的目标 Model 无法借此建立合法业务池。不同池即使指向同一 Provider，现存计数也互不相加。
- `aip_model_eval_request` 与其 `aip_request_model_eval` 原 maker/checker 审批均已存在，但后者 `executionAllowed=false`；批准事件本身不等于预算/容量预留或发送许可。

## 不可绕过的设计不变量

1. 用途身份为 `ModelEvalRequest` + 原 `ActionApprovalEvent`，不填假的 Task/AgentRun。任何 Eval 预留必须精确重验申请 hash、当前 Model head、next-active target、Suite/Contract、Provider/Price/Quota/Budget、checker、审批期限与撤销。普通业务仍走原 Route active/Eval gate。
2. Eval 的费用占额写入原 `aip_budget_bucket`，日/月账户使用 `BudgetPolicyRevision.budgetRevisionRef.resourceId`，与业务调用的 BudgetRevision ID 相同；Eval 独有的单申请上界作为第三个 task-kind 账户，以 `model-eval:<request_id>` 命名，但不得将它记成 Task。三桶锁定顺序与原 Store 相同，未知不释放。
3. 物理并发上界必须有独立、可追溯的 Provider 容量权威，不能拿某 Route 池上界冒充 Provider 上界。普通 AgentRun 和 Model Eval 在同一个 `(tenant, provider instance)` 容量账户行锁及同一占用账本计数；普通运行还保留 exact Route 池限制。若 Provider 物理上界/身份缺失，所有新 Eval 发送禁入；迁移后的普通运行不能绕过共享门。
4. 锁顺序固定为 Model/批准 head 重验 → 三预算桶（稳定排序）→ Provider 物理账户 → 普通 Route 池（如适用）→ 持久化预留和一次性 send intent。不能在持锁事务中调用 Provider。由于现有 `reserve()` 自开连接/提交，不能把它与 Eval 物理预留顺次调用并宣称原子；应抽取事务内复用的预算核验/桶移动内核，或以数据库过程共享相同账本与锁，而不复制独立余额。
5. Intent 只允许一次领取；`prepared` 可在明确零发送时取消，`submitted/unknown` 保持预算与物理占额并转只读对账。失联、超时、无 Receipt 不得自动重发。有效期、批准撤销、Price/Policy/head 漂移在领取前再验；普通 `AipEvalRunner` 与 Action executor 仍拒绝绕入。

## 拟议文件与分段验证

| 段 | 精确文件 | 实现/验证门 |
|---|---|---|
| b4a 物理账本 RED/设计 | 本文件；`services/aos-api/tests/aip/test_model_eval_shared_capacity_pg.py` | 先用自动创建的 disposable PG 证明同 Provider 两 Route 池可各占上界，明确现状 RED；再规定共享 Provider 账户缺失禁入、普通+Eval 合计不超限、并发锁序。测试只造隔离权威，不触真实库。 |
| b4b 容量最小实现 | 新 additive Alembic；`aip_model_capacity_reservation.py`；专用 Eval 容量 owner；相邻容量测试 | 正式 Provider 物理上界来源、发布审批、历史活跃预留切换和唯一账户先有明确权威；共享账户/账本需 FORCE RLS、不可变身份、事件与幂等。不能直接复用 agent_run_id 字段。 |
| b4c 预算与 Intent | 新 additive Alembic；`aip_budget_reservation_store.py` 的事务内共享内核；专用 Eval 预算/Intent owner；`aip_model_eval_action.py`；相邻 PG 测试 | 共同日/月桶、独立申请上界、同一事务双预留和一次 Intent；失败全回滚；未知保留占额。当前真实 Provider 身份缺失时发送仍为零。 |

## 施工前必须补证的风险

- 现有 ProviderRevision 没有物理并发上限字段；`QuotaPolicyRevision.maxConcurrency` 是 Model 治理配额，不能未经正式来源与范围确认就当 Provider 物理上界。物理账户的所有者、额度、有效期及变更审批须从正式配置/现有权威派生，不能写常数或测试值到当前实例。
- 现有 Route 池按池隔离，跨池普通运行本身可能超订；对已存在的活跃预留不能静默清零。先在隔离 PG 复现，再设计启用前全量只读盘点、旧占用映射与零执行切换门。
- Eval `BudgetPolicyRevision` 指向 `BudgetRevision`，但当前 Store 的 `ApprovalEvent` 要求 Task 绑定。专用申请批准核验应走同一 ApprovalEvent 权威，不能放宽原业务 Store 的 Task 约束；日/月桶共享需并发测试证明。
- `a0v_118` 当前真实库与代码头差 15 个迁移，b4 迁移只在 disposable PG 验证；真实迁移/重启属独立恢复波，须备份可恢复、克隆全链与零执行窗口。

本设计任务退出条件：复核上述断言并产出精确 RED 入口；未完成物理权威、预算预留或 Intent 之前，GT-b4 和真实首评均保持 pending。不得用计划完成替代代码 GREEN 或自然首链。
