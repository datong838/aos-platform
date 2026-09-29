# W5CB4 BG00ca｜网络批准原子消费预检文件级方案

## 上位与现场

复习 231/231-5、41 网络策略、BG00bs/by/bz、当前 `m1@3c5be7ef` 与 a0v117 权威库。当前正租户网络 Proposal/ApprovalEvent/策略0、第二真实 checker0，a0v116 active INSERT 门无条件阻断。本波只完成未来消费函数可复用的同事务**预检**，不写 Receipt/revision/head、不开放 active、不提供产品执行入口。当前库只读核验；合成 maker/checker 仅限显式 test-only 全库克隆。

## 修改文件和合同

1. 新增 `services/aos-api/aos_api/aip_network_policy_approval_consumer.py`，暴露仅供内部事务调用的 `precheck_network_activation(conn, scope, proposal_id, approval_event_id)`。调用方必须提供已建立的精确租户事务；检查 `current_user=aos_runtime` 与 `aos.org_id/project_id`。同事务锁 Proposal，读该 Proposal 的所有 ApprovalEvent/WithdrawalEvent 与现有 Network Receipt；仅接受一个精确 approved Event、当前 Proposal approved 且版本=Event决定前版本+1、双期限未到、无后续拒绝/撤回、Proposal/hash/binding/policy hash 与 Event 一致。固定 Receipt operation+proposal_id 键若存在即拒绝预检。复用现有 `NetworkPolicyApprovalGuard` 重验元数据、当前 maker/checker成员、head/Egress/目标及 draft，避免复制权威逻辑。返回不可执行的证据快照，不宣称授权写 active。
2. 新增 `services/aos-api/tests/aip/test_aip_network_policy_approval_consumer_pg.py`：显式 test-only `aos_bg00bx_cutover_testonly_20260930`，先 RED；在该克隆创建合成 maker/checker 和合法 Egress，正式 Producer/Checker 产生一个批准 Event，预检正向；再测决定前 Event版本与当前+1、拒绝/撤回/过期、错租户/错hash、head/Egress/成员漂移、固定消费键已有 Receipt 拒绝。全部合成记录只在 clone；当前库0写。
3. 现有 `aip_network_policy_action_producer.py`、`aip_action_store.py`、a0v116/117 migration 与路由不改。测试需在专项和相邻回归后再审是否有漏项。BG00cb 独立方案才设计 DB安全函数/唯一消费和安全迁移；本波无迁移、无 Host。

## 验证/中止

正向仅说明同事务预检可读取精确当前证据；不得把它用于当前实例执行。RED→GREEN、真实 PG clone 正负、当前权威库只读行数0、active直写仍23514、API健康、编译/diff。若发现当前 ActionStore无法提供必要事件/撤销证明，保留失败封闭并修订方案，不用普通 approvalRef 文本或高权限直写代替。
