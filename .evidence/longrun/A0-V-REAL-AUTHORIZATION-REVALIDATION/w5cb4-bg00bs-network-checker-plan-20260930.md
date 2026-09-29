# W5CB4 BG-00bs｜网络策略独立 checker 的隔离接线路线

## 上位合同与事实

按 AGENTS.md、aos-engineering-delivery、231/231-5、41 网络方案、BG-00bg/bk/br 复习。正式审批必须绑定目标 revision/hash、当前独立权限、期限与撤销；当前 `aos_current_preview_20260927@a0v_115` 的正式网络 ObjectType/ActionType=0，正租户只有 maker 可候选成员，无独立 checker。BG-00br 已能在 test-only 生成 R2 drafted Proposal，通用 checker/executor 明确禁入。本波只接专用 checker 决定入口，并在隔离克隆作正负路径；不接策略 active/消费/Host。

## 文件级计划

1. `services/aos-api/tests/aip/test_aip_network_policy_action_producer.py` 与 `_pg.py` 先 RED：通用 decide、非 OIDC、同人 maker/checker、无当前成员/角色、提案 hash/version、元数据/head/Egress/binding 漂移均拒；test-only 独立 checker 对精确 drafted Proposal 批准一次、同键重放、不同键冲突；另一决定拒绝已批准提案使状态失效，通用 executor 仍禁入，策略表零写。此处合成账户只证代码，不能算正式批准。
2. `services/aos-api/aos_api/aip_network_policy_action_producer.py` 最小扩展独立 checker guard：必须 OIDC；在 Store 决定同一租户事务里读取当前 `meta_membership` owner/admin、精确元数据、锁定当前 head 并重验 Egress 与 target/binding；Proposal stable draft snapshot、policy/hash、maker 不可漂移。若远端 OpenFGA 启用但无同事务校验器，失败关闭。期限用既有 ActionStore 的 proposal/approval expiry，不自造批准表。
3. `services/aos-api/aos_api/aip_action_store.py` 保留无专用 guard 时所有固定策略动作通用 checker 禁入；仅 exact NetworkPolicy guard 可走既有 `decide` 和 ActionApprovalEvent，checker 的资格必须由当前 DB 返回，不使用请求角色自证。执行租约继续禁入。
4. `services/aos-api/aos_api/routers/aip_runtime_guard_policies.py` 增专用 `/networks/activation-proposals/{proposal_id}/decision`，经认证 Principal、幂等键、现有 DecideActionProposalRequest；当前 dev token 403，缺正式元数据/成员保持失败关闭。无策略发布副作用。
5. 专项/相邻回归、test-only PG、真库只读/最新 API、代码与方案复审、verification、精确提交、01/06/D-waves/authority。无 DB migration。

## 风险与停止线

通用 ActionStore `decide` 对批准事件的到期会写期限，但没有单独的“撤销批准事件”表；本波只用后续独立 reject 决定使 Proposal status=`rejected`，这能阻止租约，历史批准事件保留。不得声称已经有完整审批撤销 authority 或可消费。当前实例仍缺正式受控元数据与第二人身份，正向只能在 test-only 克隆；之后原子消费必须重查批准未失效、Egress/head/安装代次及一次性 Receipt，另立独立波。
