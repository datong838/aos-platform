# W5CB4 BG00by｜网络 checker 当前依赖重验修复方案

## 事实与范围

复习 231/231-5、41 网络审批、BG00bs/bt/bv 和当前 `aip_action_store.decide`。当前 m1 `4c165434`、权威库 `a0v_117`，固定元数据已注册，正租户正式网络Proposal/ApprovalEvent/head0；第二真实 checker 仍缺。`NetworkPolicyActivationGuard.check_replay` 目前只做 row 形状检查；本应重算风险、元数据、maker当前成员、head/Egress/目标 binding 的代码误放在 `NetworkPolicyApprovalGuard.check` 的 return 之后，永远不可达。这使 maker 提案后依赖漂移时 checker 可写批准事件，不能等消费阶段才发现。

## 文件级 RED/最小实现

- 修改 `services/aos-api/aos_api/aip_network_policy_action_producer.py`：将不可达的 body/risk/policy/binding 重验代码移入 `NetworkPolicyActivationGuard.check_replay` 可达路径，保留现有 `NetworkPolicyApprovalGuard`、ActionStore 决定事务和错误码，不重写协议。
- 修改 `services/aos-api/tests/aip/test_aip_network_policy_action_producer.py`：先 RED，使用精确 row 与 guard stub 证明 `check_replay` 必须调用 `check_request`，依赖漂移拒绝；随后跑现有 checker专项。
- 修改 `services/aos-api/tests/aip/test_aip_network_policy_action_producer_pg.py`：在显式 test-only `aos_bg00br_producer_testonly_20260929` 增加“正式提案之后 head 变化再决定”负例，拒绝审批事件并对账；再跑既有 PG 正负路径。当前真实库只读，不造真实用户，不写 Proposal 或策略，不启 Host。

## 判据与风险

新测试从失败到通过；现有专项/相邻回归通过，代码复审确认 check_request 在同一 Store 决定事务内被调用且会锁 head、查当前 metadata/maker成员/Egress、复算 binding；current active DB insert门保持。此修复仅缩小审批时漂移窗口，不提供独立撤销事件、一次性消费 Receipt 或正式 checker；后续仍要在消费事务重验。方案不涉及新迁移，当前实例API需安全重载并读回健康。
