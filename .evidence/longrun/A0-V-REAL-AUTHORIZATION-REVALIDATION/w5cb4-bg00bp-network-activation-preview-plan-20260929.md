# W5CB4 BG-00bp｜NetworkPolicy 只读激活预览方案

## 方案复习与事实

遵循 AGENTS.md、aos-engineering-delivery、231/231-5/231-9、BG-00bi/bj/bk/bm/bn/bo。当前 `org-org/dev-project` 真库为命名卷 `aos-a0v-recovery-pg-data`、a0v_115；正式策略 ActionType/Producer/Approval/Consumer 为 0；通用 Action 与数据库保留门已拒绝五固定 ID，Network Store 的 active 发布仍 422。预览仅帮助看到精确目标与阻断项，不是批准、配置发布或 Host 准入。

## 文件级计划

1. `services/aos-api/tests/aip/test_aip_network_policy_activation_preview.py`：先 RED。覆盖租户隔离查询、当前 head 版本/候选修订漂移、目标 hash 确定性、出站依赖缺失仍显式 blocker、形式审批/消费者未就绪恒 blocker、数据库零写。
2. `services/aos-api/aos_api/aip_network_policy_activation_preview.py`：新增只读服务，使用现有 `NetworkPolicyRevisionCreate`、精确 target 合同与 Store 的 scoped head/dependency；结构化返回候选哈希、binding hash、head、阻断项。所有预览结果显式 `activationAllowed=false`，不得制造可消费 Receipt。
3. `services/aos-api/aos_api/routers/aip_runtime_guard_policies.py`：只增加经 `require_principal` 的 `POST /networks/activation-preview`；沿用 `If-Match` 整数版本解析。禁止调 `publish`、Action create/decide 和任何执行。
4. 专项+邻接回归、静态/差异检查；如服务热更则以最新 m1 重启 API，验证只读 HTTP 与原 active 422，真实库仍 0 policy action/operation/binding。verification 落盘，精确 m1 提交；01/06、D-waves、authority 同步。

## 风险、边界与回滚

读取当前 head 与依赖不提供可用于执行的事务锁；结果仅快照，提交后仍需未来独立 Producer、maker/checker、期限/撤销、同事务一次性消费重新验证。`approvalRef` 文本不提供任何准入。当前真库只读，无新迁移、无 Host/worker/Provider、无商城源和旧 Run。回滚为移除独立预览服务/路由，不改变 Store active 门和权威数据。
