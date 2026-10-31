# T2 四策略 revision 2 draft 实际续期方案 r884

时间：2026-10-31（Asia/Shanghai）

## 目标与资格

在 canonical 隔离库 `aos_refresh_activation_native` 中，沿原 `AipBudgetAuthorityStore`、`AipRuntimeGuardPolicyStore`、`AipModelGovernancePolicyStore` 依次发布四个 revision 2 draft。固定正向租户 `org-org/dev-project`，current head 必须仍为 revision 1/version 1/draft；新窗口 `2026-10-31T14:50:00Z` 至 `2027-03-31T04:00:00Z`。不激活、不批准、不调用 Provider/模型。

主写归属活动 Task `qyh-m2-native166-original-history-actual-20261027-h1029-h1031`，源码归属 `qyh-m2-three-backend-runner-20261023-h1027-h1029-h1031`。新建短生命周期连接 companion Task，仅持有 `18458 -> exact CID:5432`、本线程 SSH 进程及独立连接证据；不得借用 `18455` 或旧连接 Task。

## 最小实现

1. 新 actual driver 只组合已提交的 `t2_policy_draft_renewal_r883.py`、原三个 Store、原 `consumer_connection`、原 `_TenantPolicyConnection` 和原 `DurableActivationJournal`。
2. `RenewalJournal` 仅覆写 identity、四步 descriptor 与 receipt ID 校验；复用原 O_EXCL、fsync、哈希链、attempt/settled、OBSERVE/RECONCILE/ISSUE/COMPLETE 状态机，不复制安全状态机。
3. 每步写前重新读取对应 current head/revision payload，必须精确等于冻结 revision 1；先写 attempt，再调用原 Store `publish(... expected_version=1)`；known return 后由独立读取验证 Receipt、request hash、result ref 和 materialized revision 2，再写 settled。
4. 若 attempt 后没有 settled，下一次只能只读查新幂等键：精确 Receipt 存在则 settle；不存在或漂移即停止，不重发。
5. 原 Store 每步独立提交，因此 journal 是跨提交恢复权威；不能伪造四步原子性，也不能在失败后执行后续步骤。

## RED/GREEN 与文件

新增：

- `.evidence/qyh-m2-three-backend-runner-20261023/t2_policy_draft_renewal_actual_r884.py`
- `.evidence/qyh-m2-three-backend-runner-20261023/test_t2_policy_draft_renewal_actual_r884.py`
- actual intent/result/journal 与独立连接证据

RED 覆盖：错 owner/thread/head/task、错租户/时间窗、旧 key、head 漂移、active 候选、attempt 后无 Receipt 禁止重发、Receipt/hash/ref 漂移、步骤乱序、已 complete 再执行。GREEN 后运行上轮 11 项、原 draft 16 + 11 subtests、journal 原专项及静态编译。

## 实际顺序与停止规则

1. 固定当前 handoff/HEAD/dirty/index、两主 Task/Lease、源码 SHA、容器 ID/IP/卷/网络、四 current heads；生成 intent 后不得修改源码。
2. 登记连接 companion Task，创建当前无 ControlMaster SSH 配置，启动唯一 `18458` 转发并核 PID/argv/listener。
3. 只读身份检查：restricted migrator、PG16/OID16384/cluster exact、正向 tenant、四 current heads exact、旧 Receipt keys存在且新 keys为0。
4. 单次运行 driver。known success 后另起只读事务验证四 head=revision2/version2/draft、截止精确、新 Receipt各1、旧revision1与旧Receipt仍在、active数0、刷新历史仍0、dev-org不可见。
5. 关闭精确 SSH PID并确认监听消失，完成 companion Task。

任何身份、Task/Lease、SHA、head、Receipt、事务、权限、unknown 或清理漂移立即停止；不修库、不改角色、不重发已 attempt 步骤。结果只证明四个 draft 续期，不是本人批准、策略激活、M2、真实经营链或阶段验收；工程2/8、真实0/8保持。

## 执行结果（2026-10-31 22:53 北京时间）

- 唯一 fresh 执行按 `budget → egress → data → quota` 返回 `ISSUE/ISSUE/ISSUE/COMPLETE`，`unknown=false`；每步 attempt 与 settled 均已落入 r884 不可变 Journal。
- r885 只读恢复重新打开同 Journal，四项 facts 与 fresh 结果逐字一致；r886 独立只读 SQL 确认四个 head 均为 revision/version 2、八条 revision 行保留 1/2 两版、revision-2 仍为 draft 且有效至 `2027-03-31T04:00:00Z`。
- 新 Receipt=4、active policy=0、refresh receipt=0、dev-org 对 org-org 正向策略行可见=0；未批准、激活或调用 Provider/模型。
- 临时 18458 SSH PID 51712 已关闭，进程与监听均不存在；连接 Task 已 Delivery。
- 结果与本方案一致，不改变工程2/8、真实0/8。下一硬缺口仍是本人原生批准和原 Owner 链自然生成至少两条刷新回执。
