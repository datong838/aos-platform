# W5CB4 BG-00bs｜网络策略独立 checker 隔离验证

## 方案、代码与 RED

- m1 `3902c665` 文件级方案先行，`98a8e46d` 最小实现。复习 231/231-5、41 网络方案、BG-00bg/bk/br 与 ActionStore decide/ApprovalEvent/执行租约。当前真实库保持只读，策略消费未接。
- 新专用 checker 函数缺失的 RED 退出1；拒绝决定的同键 replay 因提案已 `rejected` 被错误拦截，RED 退出1；无时区的 `approvalExpiresAt` 被送进 Store，RED 退出1。修复均限于专用 guard/输入门。通用 checker 与 executor 保持禁入。

## 自动与 test-only PostgreSQL 结果

- 专项+相邻 `test_aip_network_policy_action_producer.py`、`test_aip_policy_action_proposal_gate.py`、`test_aip_runtime_guard_policy_api.py`、`test_aip3b_action_execution.py`：**29 passed，退出0**；最后修改后专项 **10 passed，退出0**。`compileall` 与 `git diff --check` 退出0。
- 复用基于当前只读 dump 的独立克隆 `aos_bg00br_producer_testonly_20260929`，仅在该库放入合成 NetworkPolicy 元数据、maker、第二 checker、第三 revoker 和 active Egress。直接运行 PG 正负路径退出0，输出 `bg00bs_postreview_clone_green`：maker/未知成员拒绝；版本 CAS 拒绝；独立 checker 获得唯一 R2 approved ApprovalEvent，其 action binding hash 等于原 Proposal；同键批准及拒绝回读，键漂移/第二人重复批准拒绝；第三人拒绝已批准提案后状态为 `rejected`；Network head/revision/receipt 始终0。这是**隔离代码路径证明**，不代表正式账户、批准或业务执行。
- 既有 ActionStore 无单独的审批撤销事件，当前只证明后续独立拒绝决定使 Proposal 失效，历史批准事件仍保留；不得把此结果写成“完整撤销权威”或可消费批准。

## 当前实例与最新服务只读复验

- 实现提交后以原签名 Receipt 重启 API，启动日志回读 `database=aos_current_preview_20260927`、`migrationMode=disabled`、`runtimeHost=0`、`workersEnabled=0`。8080 PID12713、8434 PID4658 监听，18181 无监听；OpenAPI HTTP200，专用 checker 路由存在；dev 身份请求得403 `OIDC_POLICY_CHECKER_REQUIRED`，在进入业务数据库前拦截。
- 当前权威库只读查 `current_database()=aos_current_preview_20260927`、`alembic_version=a0v_115`；NetworkPolicy ObjectType=0、ActionType=0、正租户同类 Proposal=0、所有正租户 ActionApprovalEvent=0、Network head=0。当前实例无正式审批正向，八配置、Host、自然首链仍未达。

## 复审、风险与下波

- 专用决定在同一 Store 事务里要求 OIDC、不同 maker 的当前 owner/admin 成员、当前精确元数据/head/Egress 与不变的 Proposal/draft/hash；实际审批资格由 DB 成员返回，不信请求 roles。期限、幂等、版本和 ApprovalEvent 复用现有 Store。通用入口无 guard 即失败关闭，策略 active/执行租约不开放。
- 仍缺当前正式元数据合法登记来源、第二位真实 checker、完整撤销权威、一次性原子消费 Receipt、安装代次/Host 与八配置。browser-pilot 不可用，本波未做浏览器截图交互验收。
- 下一波 BG-00bt：先只读审 active NetworkPolicy Store 的数据库禁入门、ActionApprovalEvent 精确消费与恢复边界；方案/RED/test-only 才考虑独立原子消费最小点。当前真实库写入/迁移须另波一致备份和全链克隆，Host继续关闭。
