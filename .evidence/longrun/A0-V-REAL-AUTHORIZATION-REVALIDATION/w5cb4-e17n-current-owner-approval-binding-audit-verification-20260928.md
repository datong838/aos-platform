# W5CB4 E17-n｜当前 Owner、安装审批与配置绑定只读审计

## 合同区分

- `bundle_installation_revision` 当前 state/decision 指安装方案获批；当前 instance 为 revision 3 `approved`、active_revision null。`bundle_installation.created_by` 与 `requested_by` 均是 `a0v-current-preview-install-maker`，不可变 decision actor 为 `a0v-current-preview-install-checker`。这张 decision 不等于 runtime-apply/enable 的审批 Receipt，也不等于自然业务执行批准。
- `extension_runtime_operation` 存 runtime-apply/verify/configure/enable 等操作及 `requested_by`、`approved_by`、`approval_ref`；`extension_runtime_binding` 持 generation、config_ref、enabled/fence；`extension_runtime_configuration` 持不可变配置修订。当前这些表在精确租户均为 0。
- `PendingPreparationDirectory` 只从待投递的 runtime-apply outbox 或有效 rehydrate binding 找描述符；`LiveInstallationOwnerFactory` **在此后**创建进程内 `LiveInstallationLifecycleOwner`，后者持有 `PreparedJob` 并处理 verify/enable。它不是 Host 启动前的持久“Owner 凭据”。E17-m 文档里的“正式安装生命周期 Owner 前置”需在下一波改写为“当前安装/操作审批事实、精确绑定及可信进程 Owner 构造路径分阶段验证”，避免循环依赖。当前硬禁入仍应保留。

## 当前库只读回读

使用 `scripts/a0v_current_preview_bootstrap.py:_connection_parameters()` 取得固定当前卷的连接参数，`psycopg` 连接后先 `conn.read_only=True`，只查 `org-org/dev-project` 的计数/非敏感安装字段。首次查询因误把 `bundle_installation_revision` 当作有 `approved_by` 列而退出 1；回读 schema 后改从 `bundle_installation_decision.actor` 取批准者，复核退出 0。

| 事实 | 结果 |
|---|---|
| 数据库 | `aos_current_preview_20260927`；代码/库迁移 `a0v_109` 已由 E17-l 签名预检复核。 |
| 安装 | `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`，current revision 3，state `approved`，active revision null；maker/checker 均为当前 preview 名称，互异。 |
| Runtime | `extension_runtime_operation=0`、`extension_runtime_binding=0`、`extension_runtime_configuration=0`、`extension_runtime_host_assignment=0`。 |
| Action | `aip_action_proposal=0`、`aip_action_approval_event=0`、`aip_action_receipt=0`。 |

## 下一波精确问题

E17-o 先确定 Host **空闲启动**的安全前置：当前签名/物理库/三身份/固定 OCI/Host assignment 与当前安装批准版本如何绑定；哪些正式 runtime 操作由 API 先建立、哪些由 Host 后处理；四源配置何时提交与生效；业务 worker 如何在未就绪安装/预算/来源时保持禁入。先文件级设计与失败测试，不能把八候选计数、preview decision actor、运行进程 Owner 对象或空表冒充完整授权；当前 `FORMAL_OWNER_AUTHORITY_UNPROVEN` 保留至这些合同得到正反验证。当前库只读，未启 Host/worker、未碰旧 12 Run 或商城源。`browser-pilot` 截图待补。
