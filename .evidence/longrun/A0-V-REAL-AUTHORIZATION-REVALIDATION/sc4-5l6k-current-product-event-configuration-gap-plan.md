# SC4-5l6k 当前 ProductEvent 正式配置缺口补充方案

日期：2026-09-15  
基线：`f00cfe9f`  
owner：`m1`；不 push；230 L0 挂起。

## 已验证事实

E installation `1c08edfb-ec0d-4abb-a411-7b6ec0d6066a@5`、generation `ebaa620a-8831-4c2a-b971-788383f352f8` 已 ready/enabled/unfenced。真实 P02 Run `scr-a5a23c835eb04a73` 只读取得 65 个商品对象并成功写入 Dataset，57 active、8 deleted；command/derived/dataset 为 1/1/1，recovery claim 为 0，canary 为 0。

ProductEvent Worker 没有产生 Occurrence、Case 或 Run。主库读回证明当前租户不存在 `ecommerce_investigation_schedule_policy_head` 和 `automation_schedule_binding`；这不是源读取失败，而是安装后的真实业务配置尚未建立。

当前 canonical shop refs、`initial_store_analysis` profile/scope、该 profile 的职责与阶段模板已经存在。Case selection 的公开预览因十二类 SourceReadiness 未完成而显示 `SOURCE_READINESS_NOT_READY`；领域包的 `ecommerce_growth_case_put` 正式 Host 入口仍允许建立 DRAFT Case，后续分析必须用原 `WAITING_DATA`、DataRequirement 与恢复链表达数据不足，禁止伪造 readiness。

首次经 canonical router 提交 Case 时平台以 `EcommerceGrowthHostBlocked: current dispatch is not executable` 拒绝，且 Case 零写。主库读回进一步证明九项 `extension_operation_dispatch_binding` 全部仍为 `handler_kind=legacy`、`operation_fence=true`、revision 1，installation/generation 为空。当前 E 的 runtime ready 不能替代正式 Host dispatch 权威；任何直接调用 Store/Host port 的做法都会绕过安装边界，禁止使用。

旧 installation `97aeb2e7-59ba-40f6-89a3-fb0293bc0497` 仍持有一笔未使用、可撤销的 first-dispatch registration；其状态为 `registered`、`allowedActions=[withdraw]`、`executable=false`。当前 E 为 `unregistered`。因此必须先正式撤销旧的 pristine registration，再以 E 的 current installation revision、generation、binding revision、execution epoch 和 config exact ref 注册九项 fenced legacy 起点；之后才能执行 exact activation cutover。

旧注册撤销后，E 的首次注册被 `REGISTRATION_GROWTH_DECLARATIONS_INVALID` 安全拒绝且零注册写入。签名 growth 1.8 包确实完整声明了九项受控经营 API，同时还合法声明了独立的 `analyst_workspace_view_v1` 只读工作台 API；资格函数却把“选中九项经营声明”写成了“整个包只能有九个 API 声明”，导致包增加无关 API 后无法注册。资格校验应只筛选 `_API_PATHS` 所属九项，并继续要求数量、operationId、method、path、mode 全部 exact；完整包声明摘要与签名复验仍覆盖包括工作台 API 在内的所有 backend contributions，不能削弱。

当前租户只有 `a0v-ecommerce-growth-1.4-runtime-owner=admin` 与 `user:dev=owner`。运行时 owner 必须执行且不能批准自己的执行；当前审批门的 checker 角色只接受 `admin/approver/aip_approver`，而 workspace 正式成员模型只提供 owner/admin/editor/viewer，故两名现有成员不能组成 maker/checker/executor 三方链。应由现有 tenant owner 经正式 workspace member 入口增加一个用途受限的 checker 身份，角色为 admin；不得改原两名成员角色。全局 `meta_action_type` 尚缺 `ecommerce_growth_schedule_put` 与 `ecommerce_growth_event_control`，而现有包 manifest 只有 actionTypes 权限声明，没有动作类型定义随安装落地。这些都是“可安装、可重装后无需开发者接线”的真实生命周期缺口，必须进入后续包配置计划。

首次 reviewer API 调用在 18181 的 TWA memory 模式返回成功，但安装控制的 `meta_membership` 读回仍只有 runtime owner 与 `user:dev`，因此 checker 审批被 `INTERNAL_CONTROL_CURRENT_AUTHORITY_REQUIRED` 拒绝。真实链必须把受控 API 以既有 `AOS_TWA_STORE=pg` 启动，再经同一 workspace member API 重放 reviewer 配置，并要求 `meta_membership` exact 读回；内存 member 不能作为权限证据。已创建但未完成的 cutover proposal 必须按原 idempotency key查回复用，审批 expiry 从已存 proposal 固定推导，禁止因重试时间变化新建 proposal。

PG 模式重放又暴露 `ensure_tenant_catalog_schema()` 错误继承 HTTP 请求的 tenant context：无参 `connect()` 因 contextvar 自动应用 scope 并降为 `aos_runtime`，随后 `CREATE TABLE IF NOT EXISTS` 被 schema 权限拒绝，成员 API 仍只更新内存。schema bootstrap 属于控制面 DDL，必须用 `connect(inherit_scope=False)`；实际 member upsert 继续使用当前租户事务，不扩大 runtime 角色权限。

R3 approval exact ref、版本和 hash 已从主库验证一致，但 cutover prepare 仍报告 approval 不存在。原因是 Store 以 `aos_extension_maintainer` 查询启用 RLS 的 AIP proposal/approval/draft 表，而这些 tenant policy 只对 `aos_runtime` 生效。审批读取与 current revalidation 必须在同一 serializable transaction 内临时切换到该注册身份本就拥有的 `aos_runtime`，随后恢复 `aos_extension_maintainer` 执行 cutover；不增加 grant、不绕过 RLS，异常由整笔 transaction 回滚。

角色修复部署后首次真实 prepare 又按预期拒绝：原两笔 approval 的 30 分钟有效期已经结束，而 proposal 尚未到期，切换表仍保持零写。AIP 明确禁止同一 checker 对同一 proposal 重复批准，因此恢复动作不得覆盖旧 result、删除旧事件或复用旧审批 key；必须以相同 action type、payload、maker 和双 checker 创建新的 R3 proposal，冻结为独立 refresh intent/result，并让后续 prepare 只消费最新 refresh approval exact ref。旧 proposal 与过期 approval 保留为失败恢复审计证据。

原 prepare intent 已绑定过期 approval exact ref，虽然服务在写入 cutover operation 前拒绝，它仍是不可变请求证据。刷新审批后的 prepare 必须使用新的幂等 key 和独立 refresh intent/result；后续 pause/commit 只消费成功的最新 prepare Receipt，不能改写或删除首次失败 intent。

刷新后的 prepare/pause 成功，数据库 commit 函数随后暴露既有版本契约错误：AIP 每写一笔 approval event 都先记录当时 proposal version，再把 proposal version 加一；因此当前最后一笔审批恒满足 `proposal.version = approval.proposal_version + 1`。`ar2_014` 却要求两者相等，使正式 AIP 产生的单审批和双审批都无法通过数据库最终门。新增 `a0v_051` 只修正这一项等式，保留 approval exact ref、未过期、proposal hash、action binding、payload、九项 dispatch、drain 和 Receipt 等全部校验；应用层 current approval validator 继续在同一事务内验证全部独立 checker 及其实时安装权限。PG 回归必须覆盖新等式，并证明旧的漂移版本仍拒绝。

`a0v_051` 上线后的逐条件诊断确认版本等式已经成立，剩余拒绝来自第二个历史契约差异：直接 `create_proposal` 路径的 stable snapshot 在没有来源草稿时不写 `sourceDraftRef` 键，而 `ar2_014` 只接受显式 JSON `null`。应用层 canonical 校验已把“缺键”和 `None` 视为同一无来源语义，proposal 的三个 source draft 列也全部为 NULL。新增 `a0v_052` 将数据库函数对应比较改为 `COALESCE(snapshot->'sourceDraftRef','null'::jsonb)`；有来源时仍要求三列和 exact ref 全等，其他校验不变。当前系统策略实际把 internal cutover 定为 R2/minimumApprovals=1；本次人为执行了两名独立 checker，证据中按真实策略记录，后续生命周期设计再单独评审是否把风险 floor 提升到 R3，禁止把当前 R2 伪记成 R3。

两轮诊断和迁移超过了刷新 approval 的有效期；当前操作已完成 prepare/pause，状态为 `draining`，九项 dispatch 仍为 fenced legacy，运行时已按协议 drain。现有模型没有“审批过期后续签”入口，直接改 operation、prepare Receipt、pause Receipt 或 approval expiry 都会破坏不可变历史，禁止使用。新增 `a0v_053` 的 `extension_dispatch_cutover_approval_refresh_receipt` 作为每个 activation operation 一次的不可变续签权威：请求必须引用原 prepare Receipt 和新的当前 ActionApprovalEvent；服务在同一事务内复验原 operation/Receipt、完全相同的 cutover payload、当前 checker 权限和新审批，再写 refresh Receipt，不改旧表。commit 数据库函数与应用层后续锁统一优先消费经过 content hash 复验的 refresh approval ref；缺少 refresh 时保持原逻辑。漂移 payload、过期审批、跨租户、重复不同请求和 refresh Receipt 篡改全部拒绝。

## 本次主路径

1. 扩展现有私有状态执行器；每个 action 先冻结 0600 intent，再通过正式 Store、AIP Action 与当前 canonical router 执行；存在 result 时只读，不以新 key 重发未知结果。
2. `configure-brief` 创建并冻结“栖月汇全店基线与商品尖刀验证”真实 TaskBrief，来源引用本次 P02 Dataset/Run，目标是识别商品结构、在售/下架变化和后续数据缺口，不预填经营结论。
3. `transfer-registration` 先读回旧注册及其 Receipt，要求状态精确为 pristine/withdraw-only、九项 dispatch 仍是同一 fenced legacy group；以固定 idempotency key 正式 withdraw。随后从 current E 安装、revision、runtime binding 与 config ref 构造 `FirstDispatchRegistrationRequest`，正式 register 并读回 exact registration Receipt。每个远程写阶段分别冻结 intent/result；未知结果时只允许按原 key 读回或幂等重放。
4. `approve-cutover` 先通过正式 ActionType 入口确保 `ecommerce_growth_cutover` exact 定义。平台将 cutover 固定判为 R3：制单者必须有 installation apply 权限，且至少需要两名不同于制单者、彼此不同、当前仍有 installation approve 权限的 checker。故由已有 runtime owner/admin 制单并执行，新增第二个用途受限 admin checker，与已建立的第一 checker 分别批准；`user:dev=owner` 只负责通过 workspace 正式入口幂等建立 checker，不冒充安装控制制单者。proposal 精确绑定 E target、九项有序 operation、cutover group/revision、runtime revision、policy exact ref 和 registration Receipt ref。
5. `cutover-prepare/pause/commit/validate/resume` 使用平台 `ecommerce_growth_cutover_service`，按独立不可变 intent/result 串行推进。checkpoint 只记录 legacy canonical-router/version 1；无 pending target Receipt；prepare 必须验证 first registration 与当前 approval，resume 后九项必须全部指向 E、extension、unfenced，并通过 service replay 复读。
6. `configure-case` 使用当前 shop/profile/scope exact refs，经已完成 cutover 的 `ecommerce_growth_case_put` 建立唯一 `initial_store_analysis` DRAFT Case，再走既有 Case lifecycle 正式 transition 到 ACTIVE。脚本不得直接插 Case 表；之前被 fence 拒绝的 intent 原样保留并在 cutover 后以同一业务对象重试。
7. `configure-reviewer` 由 `user:dev` 经运行于 PG 模式的正式 workspace member 入口幂等建立两个用途受限的 admin checker，并从 `meta_membership` exact 读回；第一 checker 用于业务 R2，两个 checker 共同用于 cutover R3。`configure-action-types`、`configure-brief` 沿用已完成结果；两个 Case 动作类型与 cutover 动作类型均须 exact 匹配。当前补写不宣称已解决包重装配置。
8. `approve-schedule` 由 `user:dev` 创建 R2 schedule proposal，payload 精确绑定 caseId、schedulePolicyId、policyHash、expectedPolicyRevision、expectedCaseVersion；由专用 checker 独立批准，审批窗口限制在一小时内。
9. `put-policy` 从当前 E SourceSelection、current Case、签名包中的 `ProductEventSchedulePolicy` 与 `prepare_event_case_binding` 生成 revision 1 policy/successor，经当前 scoped canonical router 保存；不得直接写 policy 或 Case revision。
10. `approve-control` 对完整 enable command（移除 approvalRef 后）形成独立 R2 proposal并批准；`enable-event` 经 `ecommerce_growth_event_control` 建立 current binding。
11. `observe-event` 只轮询正式表与 Worker 状态，等待自然创建 ProductEvent occurrence、analysis entry/Run；禁止脚本调用 Worker 内部方法或写 occurrence/run。

## 身份、租户与副作用边界

- 正租户固定 `org-org/dev-project`；`dev-org/dev-project` 只做相关表零写检查。
- TaskBrief 可由当前 tenant owner `user:dev` 冻结；Case、schedule policy 与 event control 必须以 SourceSelection 当前 actor `a0v-ecommerce-growth-1.4-runtime-owner` 执行。
- R2 三方分离：`user:dev` 只制单，专用 checker 只审批，runtime owner 只执行。审批必须绑定当前 ActionType snapshot、payload、policy hash 与 expiration。
- cutover 属于安装控制操作；其 proposal 不绑定业务 Task/Run/impact preview，并额外接受当前安装 APPLY/APPROVE 权限、ActionType snapshot 与 registration Receipt 联合校验。它使用 R3 双 checker，不复用 schedule/control 的业务 R2 proposal；制单者可在批准后以 runtime owner 身份执行，但任何批准者均不得等于制单者。
- 仅允许内部任务、审批、Case、策略、绑定和分析链状态写；无商城写、发布、触达、投流、改价、库存、订单或履约副作用。
- 首次有效事件后的 occurrence、Run、DataRequirement 与恢复必须由独立 Runtime Host 的 Worker 自然产生。

## 代码范围与 preHash

- `scripts/a0v_qyh_current_product_event_first_chain.py`：`b7d2d6612841ec3fc376ce476cfe2a6f5636bb1055bab10748029796c12b3de7`
- `services/aos-api/tests/extension_runtime/test_a0v_qyh_current_product_event_first_chain.py`：`56a504025b7de9b499c8aad99e85c6361a9c05eb6fb4126cbda99d817a61238b`
- `services/aos-api/aos_api/ecommerce_growth_registration_qualification.py`：仅把注册资格的九项筛选范围与九项所有权对齐；完整 release signature/fingerprint 复验保持不变。
- `services/aos-api/tests/extension_runtime/test_ecommerce_growth_registration_qualification.py`：增加带独立 API contribution 仍可验证、九项自身漂移仍拒绝的回归覆盖。
- `services/aos-api/aos_api/tenant_catalog.py`：schema bootstrap 明确不继承请求租户 scope，避免以 runtime role 误执行 DDL。
- `services/aos-api/tests/tenant_isolation/test_tenant_catalog_memory_boundary.py`：验证 schema bootstrap 的连接参数与成员持久化边界。
- `services/aos-api/aos_api/ecommerce_growth_cutover.py`：approval authority 只在 tenant-scoped runtime role 下可见，校验后恢复 maintainer。
- `services/aos-api/tests/extension_runtime/test_ecommerce_growth_cutover_pg.py`：真实 RLS/双角色路径回归。
- 本补充方案：`NEW`。

不修改 Action policy、Case Store、ProductEvent Store、Worker、Receipt、migration 或已签名包资产。签名包无需修改；资格层仍由完整签名重验证保证额外贡献不可被篡改。若现有 Host 路由无法完成上述正式配置，先落失败证据并另开最小实现方案。

## 测试与退出条件

1. 静态测试覆盖 action 顺序、固定身份、不可变 intent/result、旧注册 pristine 撤销、当前 E 注册、cutover 五阶段 exact Receipt 串联、当前 E refs、真实 TaskBrief 来源、R2 maker/checker 分离、policy/control payload exact 绑定、canary 零写和无 Worker 直调。
2. 相关 ProductEvent approval、Host、control、router 与执行器测试通过；AR2 五类静态扫描保持为零。
3. 旧注册已正式撤销，E first-dispatch registration 为 registered/activated；九项 dispatch 均为 extension、指向 E installation/generation/epoch、unfenced，cutover prepare/pause/commit/validate/resume Receipt 完整且 replay 不增写。
4. 真实 TaskBrief 为 frozen；Case 为 ACTIVE 且 schedulePolicyRef 指向保存后的 current policy；两个业务 proposal/approval 当前有效且 checker 独立。
5. current event binding enabled，引用 E installation/generation/epoch、P02 SourceSelection、Case 与 policy exact refs。
6. Worker 自然创建一次预期 occurrence 和分析入口；幂等复读不增加对象；canary 相关表为零。落证据并提交。若 event discovery 因 P02 `meta_schedule.enabled=false` 不触发，则下一波只补“已完成历史 Run 可消费、无需保持源 Schedule 开启”的产品语义方案；不得为了触发长期打开真实源调度。

## 后续必须纳入清册的生命周期缺口

当前 reviewer 与 ActionType 初始化完成后，下一轮设计包拥有的声明式配置贡献与 install/configure/uninstall/reinstall 语义：安装时幂等确保 exact reviewer/action type，冲突时拒绝；卸载只撤销包拥有且无其他引用的贡献；重装可恢复；禁入时 event binding 自动 fenced。该项未完成前，不能宣称电商包“安装后无需开发者手工接线”。
