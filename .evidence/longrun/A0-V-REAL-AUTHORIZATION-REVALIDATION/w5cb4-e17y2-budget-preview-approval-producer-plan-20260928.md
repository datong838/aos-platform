# W5CB4 E17-y2｜预算首次激活专属预览与审批生产者文件级方案

## 上位复习与当前事实

231-3 要求当前 Head、原 payload/hash、DB 时间与同事务锁；231-5 要求额度/窗口/对象/审批/费用 exact 绑定及 maker/checker 分离；231-9 BG-00 要经产品正式配置入口恢复。E17-y 当前库 `a0v_109` 预算/费用/Action 均 0、正式成员仅一个 owner。E17-x 纯合同和 E17-y 首次激活空账本只证明必要条件，不能充作正式批准。业务 Task 的 ImpactPreview 强制无关 Task/Plan 依赖，不借用它。现有 `BudgetRevisionCreate.over_budget_approver` 可为显示姓名，不能当认证 subject。

## 最小持久合同

仅针对**首次从 Draft 激活**：`aip_budget_activation_preview` 不可变行绑定租户、当前 Draft head/version、拟 active 的下一 revision 与全量 canonical hash、日/月额度、期间、maker、指定独立 checker subject、内部账本空检查时间、到期；每个不同目标须新预览。`aip_budget_activation_decision` 不可变批准/拒绝事件绑定 preview hash、同一目标 hash、checker、决定时间与失效时间；`aip_budget_activation_revocation` 可撤销已批准事件；另加幂等 Receipt。严格同租户键、不可变触发器、RLS、最小 ACL。没有 activation consumption 时它们都不写 `aip_budget_revision(active)`。

maker/checker 必须是服务端验证的 OIDC subject，均在同一租户 `meta_membership` 以 `FOR SHARE` 查到当前 owner/admin，且不同人、checker 与预览指定 subject 完全一致；dev token、缺成员、调用方自报角色拒绝。`over_budget_approver` 仅显示/业务责任字段，不参与登录身份判断。新预算未曾 active、Draft 当前、现有内部调用/预留/桶为 0 时预览可以描述“此预算在 AOS 内尚无费用”；不声称其他预算或外部账单已对账。批准所覆盖的是**未来 AOS 预算上限**，不是既往第三方账单清算。

## 文件、RED 与边界

1. `services/aos-api/alembic/versions/a0v_110_budget_activation_preview_approval.py`：从 `a0v_109` 单头追加最小四表，RLS/不可变/索引/权限与禁止 downgrade。先 RED 检迁移图和租户/append-only。
2. 新增 `aip_budget_activation_contracts.py`、`aip_budget_activation_store.py`，`create_preview`、仅 maker/指定 checker 可读的**完整预算条款预览**与 `decide/revoke`；调用 E17-y 账本门，按 DB 时刻复验 Draft/head、双当前成员、目标 hash、幂等。审批人必须能通过正式 GET 回读金额/期间/目标 hash/内部账本时间及外部用量未证明状态后再决策，不以 ID/空壳页面代替审阅。Store 不从用户 payload 取租户/actor 或 `checker_authorized`。Store 隔离 PG 负例 GREEN 后，在现有 `routers/aip_budgets.py` 增量增加预览/决策端点，避免更改全量 router manifest；公开预算 active POST 继续 422。
3. 隔离 PG RED/验收：两个测试成员可在可销毁库内建立，错租户、dev、同人、非指定 checker、旧 head/目标漂移、过期、重复 key 都无批准；正例仅产生不可变 preview/approval/receipt，预算 active 行仍为 0。无当前实例写、Host/Provider 启动或业务验收声明。

新增迁移后代码头将高于当前真实库。此波**不重启或迁移当前实例**；立即排独立下一波做一致备份、可恢复克隆全链、零执行窗口、权威卷切换后再重启最新栈。若迁移/隔离验收不足，撤回本波迁移代码，不把当前系统留在失配状态。
