# W5CB4 E17-y｜正式预算预览、批准与同事务消费施工方案（进行中）

## 上位与现有代码复习

沿 231-3/5/9 与 E17-w/x：当前真实库 `a0v_109` 只读，预算 active HTTP 422；E17-x 的纯精确合同仅是必要条件，没有正式 authority。`aip_action_store.py:decide` 有 maker≠checker、过期、当前预览检查，但 `CreateImpactPreviewRequest` 强制业务 Task/Plan/Brief/Evidence/Eval/Responsibility/Stage。预算配置不能借业务 Task 预览。`auth.py` 的 dev principal 具有 admin，OIDC 缺角色还会回退 developer；本敏感链不能仅凭 admin/dev 或调用方自报 `checker_authorized`。`aip_budget_store.py:publish` 当前直接写 append-only revision/receipt，是待受控的原子落点。

## 文件级最小施工顺序

1. 在现有预算 authority 旁设计预算**专属**预览与批准不可变合同/表，目标绑定 `BudgetRevisionCreate` 全量 canonical hash、当前 head version、金额/期间/Owner、当前成本占额与未知状态、有效期、申请者和租户。只读计算真实账本；未知或来源缺失时 blocked，不用零值补齐。表需同租户外键、不可变/唯一键/RLS 与 Receipt；不改既有 Action 业务预览语义。
2. 只允许已验证 OIDC 且具预算专用 checker 权限的正式身份决策；maker≠checker，权限从服务端当前权威读取并留审计快照。现有 `Principal.token_kind` 可区分 dev，但角色回退和组织成员权限需进一步核验；不直接复用安装 checker 或高权限捷径。
3. 激活命令在一个 scope 事务内锁预算 head、预览/批准与费用账本，调用 E17-x 必要合同并再次按数据库时间核当前性，写 active BudgetRevision、单次批准消费和幂等 Receipt。失败无部分写，未知结果只读对账；HTTP active 422 直到这条正向链和负例 GREEN 才替换。
4. 文件候选：新增 `aip_budget_activation_store.py` / `aip_budget_activation_contracts.py`、隔离迁移 `services/aos-api/alembic/versions/a0v_110_*.py`、受控 router；最小改 `aip_budget_store.py`（共享 conn 的内部发布）、`routers/aip_budgets.py`（精确命令），隔离 PG 测试与 UI 产品入口后续接。先按表/调用者精确复核，严禁一次改完整 AIP Action 架构。

## RED 与迁移安全门

先写隔离 PG RED：错租户/旧 head/目标 hash 变更/同人/dev token/无预算角色/未知费用/过期或撤销预览批准/重复 key/并发双激活全部失败且无 BudgetRevision、Receipt、副作用；正例证明隔离正式流程一次生效与回读，不能充当前实例批准。新增迁移代码使代码头高于当前库时，立即按独立波做一致备份、克隆全链和零执行窗口；在此之前不重启或升级当前库，不宣称每日最新栈已运行。当前轮先精确核现有权限/费用真实来源，再决定迁移字段，避免虚构。

## 本次只读定位与仍待核实

- `auth.py` 的 `Principal.token_kind` 可识别 OIDC/dev；`extension_runtime/current_permission.py` 和 `ecommerce_event_proposal_gate.py` 已展示同事务 `meta_membership ... FOR SHARE` 加当前 scope/标记复核模式。预算 checker 是否必须等于 `BudgetRevisionCreate.over_budget_approver`、并由哪一现有成员角色批准，仍须产品合同确认；在此之前仅实现禁入分支，不能默认 admin。
- `aip_budget_reservation_store.py` 的 `aip_budget_bucket` 含 held/submitted/settled/unknown 四个占额，`_bucket_row` 按租户/账户/期间/币种读取。预算预览必须能由稳定预算账户与当前期间映射并持锁汇总；尚未发现可直接复用的预算配置预览聚合入口，不能把无 bucket 行当已知零用量。
- 当前预算 Store 共享连接的最小重构方式，必须保持 draft 原行为、CAS 和 idempotency。

2026-09-28 18:11 CST 再次签名预检后 `conn.read_only=True` 参数化计数：`aos_current_preview_20260927@a0v_109` 的 `org-org/dev-project` 预算 Head/Revision/Bucket/Reservation/ReservationBucket 与 Action Proposal/ApprovalEvent 全为 0；`meta_membership` 只有 `owner:1`。因此当前实例连两名不同当前成员的 maker/checker 都不具备，不能把独立代码测试当授权。`over_budget_approver` 现有合同可存自然语言姓名，不保证是登录 subject；正式生产者须另显式绑定**经服务端验证的 checker subject**，不能把该字段直接当身份凭据。

### 此波先实施的受控切片

在创建审批表或更改 HTTP 前，先做**首次激活的只读账本前置检查**：新增 `services/aos-api/aos_api/aip_budget_activation_exposure.py`，在调用方传入的 scope/事务中锁当前 Draft Budget Head，确认其精确版本，并查同一 budgetId 对应的 CapabilityInvocation、Reservation 与 `budgetId:daily` / `budgetId:pilot` 桶。仅当三类记录均为 0 时返回“现有 AOS 账本无记录”；任一非零、Head 缺失/漂移、租户事务不一致均 blocked。它不宣称外部用量完整或将 `usage_known=True`，因此不能单独生成 ready 预览。隔离 PG RED 先证跨租户、缺/漂移 Head、已有桶阻断，正例只证明内部首次激活账本空；后继预算换版与真实费用上界须完整对账。此切片不添加迁移，不改变当前库或 active 422。
