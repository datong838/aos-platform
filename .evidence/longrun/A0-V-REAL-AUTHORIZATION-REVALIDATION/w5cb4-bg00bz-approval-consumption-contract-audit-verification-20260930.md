# W5CB4 BG00bz｜NetworkPolicy ApprovalEvent 消费合同只读审计

## 当前事实

按 231/231-5、41、BG00bi/bt/bs/by 与本波只读方案，m1 `892178c8`、当前库 `aos_current_preview_20260927@a0v_117`。SQL：正租户 `meta_membership` owner1、无第二 checker；网络 Action Proposal0、ApprovalEvent0、WithdrawalEvent0、NetworkPolicy Receipt0。未写当前库、未造身份、未触发网络策略或 Host。

## 代码/数据库合同

- `AipActionStore.decide` 在同一事务锁 Proposal；把决定**前** `row.version` 和 `proposal_hash` 写入 ApprovalEvent，随后 Proposal `version+1` 并更新 status。网络 R2 一位独立 checker 批准后当前 Proposal 应为 `approved` 且版本为事件版本+1；重复同键读回不会推进。不能复用 `ar2_014` 的 `proposal.version=approval.proposal_version` 消费条件。
- 专用 NetworkPolicy checker 仅允许 OIDC、非 maker 的当前 owner/admin 成员，对批准中的 Proposal 禁止第二位不同 checker 再批准；BG00by 已修复同事务当前 metadata/maker成员/head/Egress/binding 重验。Event 本身是历史事实，不等于消费时仍有效。后续拒绝把 Proposal 置 `rejected`、maker撤回置 `withdrawn`、期限到可过期；消费事务必须以最新 Proposal status/version/expiry、ApprovalEvent decision/expiry 和其它事件判定，不能仅找旧 approved 行。ActionStore 没有独立批准撤销 Event，不能宣称完整撤销 authority。
- `aip_network_policy_receipt` 现有唯一键 `(org_id,project_id,operation,idempotency_key)`，没有原生 `(tenant,proposal_id)` 唯一；Network revision 主键为 `(tenant,policy_id,revision)`。后续消费者必须固定 operation 与 `idempotency_key=proposal_id`，在同事务检查 request hash 和结果引用，或新增独立唯一消费约束；不得允许调用方任意给 key 绕过一次性消费。重复只读回原 Receipt，漂移冲突，未知结果先查账。
- a0v116 `BEFORE INSERT` active 触发器仍无条件 23514；`aos_runtime` 对 Network revision/receipt 有 INSERT，因此只加应用层审批检查不足以安全开放 active。DB门须另立可恢复迁移，只允许精确受控、同事务验证并写 Receipt 的安全函数；不可通过会话可自设 GUC 或通用高权限入口放行。提案的精确 tenant/policy id/revision/target hash/head、当前 maker/checker权限、元数据、Egress/有效期在消费事务再次重验；如供当前安装使用，安装代次的绑定与运行 fence 仍是独立后续门。

## 下一波最小清单

BG00ca 先做**不开放 active 的只读消费预检**：新增 `services/aos-api/aos_api/aip_network_policy_approval_consumer.py` 仅在显式租户事务锁 Proposal/ApprovalEvent/head，返回可消费证据或精确 blocker；RED 覆盖批准事件的前版本、后续 reject/withdraw/expiry、跨租户/错 hash、head/Egress/成员变化、重复消费键。test-only clone 正负；当前 DB只读，a0v116门保留。独立 BG00cb 再按安全迁移规范设计 DB owner受控消费函数/唯一 Receipt/active 插入门，停机备份/全库克隆/零执行窗口后才可能切当前。当前正式身份与八配置、Host/自然首链仍未满足。
