# W5CB4 BG00by｜网络 checker 当前依赖重验修复验证

## 上位与缺口

复习 231/231-5、41 网络方案、BG00bs/bt/bv、ActionStore `decide` 与当前 a0v117。当前正租户正式网络 Proposal/ApprovalEvent0、Host关闭。发现 `NetworkPolicyActivationGuard.check_replay` 只查 Proposal 行形状；本应重算当前元数据、maker成员、head/Egress、目标 binding 的代码误落在 `NetworkPolicyApprovalGuard.check` 的 `return` 后，审批可跳过提案后依赖漂移。这一发现修正了 BG00bs 的过宽结论，不触碰现有真实批准。

## RED、修复与证据

- 文件级方案 `w5cb4-bg00by-network-checker-replay-guard-plan-20260930.md` 先行。新单元测试在修复前 1 failed，具体为 `Failed: DID NOT RAISE NetworkPolicyProducerBlocked`；将不可达代码原样移入 `check_replay`，后 1 passed。
- 显式 test-only `aos_bg00br_producer_testonly_20260929` 上 PG 正负路径 1 passed。新增提案后 head 变化：专用 checker 决定拒绝 `NETWORK_CHECKER_BINDING_DRIFTED`，该 Proposal 的批准事件数0；test-only head 在 finally 删除。此为合成身份隔离证明，不代表当前正式批准。
- 相邻五组 `test_aip_network_policy_action_producer.py`、`test_aip_policy_action_proposal_gate.py`、`test_aip_network_policy_store.py`、`test_aip_network_policy_activation_target.py`、`test_aip3b_action_execution.py` → 35 passed；`compileall`、目标 `git diff --check` 退出0。
- API 用签名 Receipt 同入口重载，8080 health 200；Web8434保持运行，18181无；当前库117、正租户网络 Proposal/ApprovalEvent/revision0，未开启 active 或 Host。PG 当前库仅只读查询。

## 复审与余险

现 checker 在 ActionStore 的同一 `decide` 事务内重新核精确元数据、当前 maker成员、head/Egress与目标 binding，再由 Store 写 ApprovalEvent；普通通用 checker/executor仍禁入。`NetworkPolicyProducerBlocked` 是 ValueError，checker guard会映射为 `NETWORK_CHECKER_BINDING_DRIFTED`，仍失败关闭。缺独立真实 checker/OIDC、完整撤销事件、一次性消费 Receipt 与能安全放行 active 的受控 DB门；消费前仍须再次重验，不能把本修复当业务首链。

下波 BG00bz：只读核当前 ActionApprovalEvent 的最新决定、版本推进、批准到期及 maker撤回/后续拒绝语义，冻结最小原子消费与独立迁移边界；随后先 test-only RED 再最小实现。当前库不写业务数据、Host保持关闭。
