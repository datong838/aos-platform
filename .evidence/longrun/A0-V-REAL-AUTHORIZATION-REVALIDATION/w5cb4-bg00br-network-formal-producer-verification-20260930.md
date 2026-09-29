# W5CB4 BG-00br｜网络策略正式 Proposal Producer verification

## 基线与施工范围

- 方案：m1 `26112834`；实现：m1 `bd6176e3`。先读 231/231-5/231-9、41 网络方案、BG-00bi～bq 与当前 01/06。仅新增 NetworkPolicy 的受控提案 Producer，复用 AIP ActionStore 的事务、幂等、R2 maker-checker 规则；通用 checker 与 executor 继续禁入。本波没有当前真实库迁移或策略 active 写。
- 当前正租户为 `org-org/dev-project`；`dev-org` 只作隔离负例。当前权威库 `aos_current_preview_20260927@a0v_115`、卷 `aos-a0v-recovery-pg-data` 只读；Host、worker、Provider 关闭。

## RED 与回归

- 新 Producer 测试模块缺失：pytest 退出2。通用执行入口两个固定 ID 负例先失败，pytest 退出1；旧执行服务只禁 `ecommerce_analysis_bootstrap`。最小修复在租约和执行准备共享的 `_reject_bootstrap_action` 中禁固定策略 ID 和快照 ID。
- `python -m pytest -q --disable-warnings` 针对 `test_aip_network_policy_action_producer.py`、`test_aip_policy_action_proposal_gate.py`、`test_aip_runtime_guard_policy_api.py`、`test_aip3b_action_execution.py`：**25 passed，退出0**。
- `python -m compileall -q` 本波四个运行代码文件：退出0；`git diff --check` 和 staged diff check：退出0。

## 独立 PostgreSQL 正负证明

- 当前库一致只读 dump：`.aos-recovery-20260929-bg00br-erVDXo/aos_current_preview_20260927_a0v115.dump`，SHA256 `75d7fa0b1c1f691e5745700fedf3292aa27489dd009df63a36db5f3106cf51c0`，TOC 5609；`pg_restore --single-transaction --exit-on-error` 到 **test-only** 库 `aos_bg00br_producer_testonly_20260929`，退出0。该库只为路径验证，未作全库恢复验收。
- 在此克隆里才写入合成 ObjectType/ActionType、maker 成员、active Egress。直接调用 `test_only_clone_produces_exact_drafted_proposal_and_no_policy_write()` 退出0，输出 `bg00br_clone_positive_and_negative_passed`。精确绑定 hash 的 R2 Proposal 处于 `drafted`；同键同内容重放，同键漂移冲突；未知 maker、错 head、错 Egress、`dev-org` canary、通用 checker 均拒绝；Network head/revision/receipt 全为0。这不是正式身份或当前实例业务正向。

## 当前实例只读与最新服务

- 实现提交后按既有签名 Receipt 重启 8080 API，启动回读 `database=aos_current_preview_20260927`、`migrationMode=disabled`、`runtimeHost=0`、`workersEnabled=0`；8080 PID10868、8434 PID4658 监听，18181 无监听。`openapi.json` HTTP200 且新提案路由存在。
- 当前库通过只读连接：`current_database()=aos_current_preview_20260927`，`alembic_version=a0v_115`，`NetworkPolicyRevision` ObjectType=0、`aip_activate_network_policy` ActionType=0、正租户同类 Proposal=0、Network head=0。当前正式 Producer 因缺受控元数据必失败关闭；页面/路由存在不算正式批准。

## 复审与剩余风险

- 方案一致性：OIDC+当前 owner/admin 成员、精确元数据、同事务 head/Egress/hash 检查、15 分钟上限、幂等/CAS、R2 草稿均已接；直接 Store、通用 checker、通用 executor 均禁入。`approvalRef` 字符串未被当作批准。无真实策略 active 或 Receipt 写入。
- 当前实例正式 ObjectType/ActionType 来源、独立 checker 当前身份、批准期限/撤销、同事务单次消费仍未齐；须在后续独立波验证来源与迁移/恢复后才可启用。八配置/Host/自然首链保持 pending。browser-pilot 当前不可用，本波无截图交互证据；本波是后端受控 Producer，不宣称浏览器验收。
- 下一波 BG-00bs：先复习正式 checker 身份与 ActionApprovalEvent 方案，文件级设计并 RED；只在 test-only 证明独立 checker、撤销/期限和精确绑定，保持当前真实库只读、策略消费禁入。之后再单独设计原子消费和正式元数据来源。
