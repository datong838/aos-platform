# W5CB4 BG-00bt｜网络 active 数据库门与审批消费边界审计

## 只读上位与代码事实

- 依据 231/231-5、41 网络方案、BG-00bg/bk/br/bs，m1 `98a8e46d` 与 `aip10_004`、`a0v_115`、`a0v_111`、`ar2_014`。本波**不改代码、不迁移当前库**；当前 `aos_current_preview_20260927@a0v_115` 保持只读，Host/worker/Provider关闭。
- `AipNetworkPolicyStore.publish()` 对 active 一律抛 `NetworkPolicyApprovalRequired`，通用 API 也因此拒绝；但 `aip10_004` 给 `aos_runtime` 三张 NetworkPolicy 表的 head INSERT/UPDATE、revision/receipt INSERT。`a0v_115` 只保留五个系统 ActionType ID，没有在网络策略表设 active insert guard。当前库 `pg_catalog` 只读实测 owner=`aos_app`，`aos_runtime` 对 head/revision/receipt 的 INSERT 均 true；revision 只有 append-only/truncate 两触发器，head 无业务触发器。
- 独立克隆 `aos_bg00br_producer_testonly_20260929` 中以 `aos_runtime` 和 `org-org/dev-project` 租户 GUC 直接插入 head 与 `lifecycle='active'` revision（`payload={}`），事务内计数1，显式 rollback 后计数0，命令退出0。说明**当前 DB 层可绕过 API/Store，不能宣称 active 全链禁入**；演练不涉及当前真库或商城源。

## ApprovalEvent 消费观察

- BG-00bs test-only ActionApprovalEvent 与 Proposal 的 binding hash 相等，但 Store 写事件后推进 Proposal 版本：近期隔离拒绝样本 `approved` event.version=1、`rejected` event.version=2、Proposal current.version=3/status=rejected。`ar2_014` 现有 cutover 消费要求 `proposal.version=approval.proposal_version`，不能直接搬用给网络策略；批准后单次版本推进、后续拒绝/撤回、期限和最新事件需由网络消费者独立定义并锁定。
- 一次性消费最小必要集：同事务锁 Proposal/head，重算 exact target/binding、当前元数据/成员/Egress，校验最新批准事件及 proposal status/期限、无后续拒绝或撤回，插入按 tenant+proposal 与 tenant+policy/revision 唯一的消费 Receipt，并原子写 head/revision。重复 key 只读回原 Receipt，漂移拒绝；失败与未知只读对账。仅有 `approvalRef` 文本或 Proposal `approved` 状态不足以允许 active。

## 结论与下波

- 当前真实库只读未写、迁移头 a0v115，正租户正式网络 ObjectType/ActionType、Proposal/ApprovalEvent/head 均0；Host off。现阶段没有通过正式批准，也存在 DB 直写缺口；业务首链未完成。
- BG-00bu 优先独立完成 a0v116 **active NetworkPolicy insert DB 禁入门**：先方案、RED，再 test-only PG 克隆验证直接 active 写拒绝且 draft 旧路径不受影响；如需切换当前实例，须一致备份可恢复、克隆全链演练、零执行窗口、精确迁移与最新栈复验，不能和普通代码波混做。正式一次性消费、元数据来源和真实 checker 后续独立波；无上述条件前 Host保持关闭。
