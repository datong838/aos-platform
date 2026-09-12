# 电商宿主持续运行与故障恢复

2026-09-12。active@7 的首个时点验证通过，但 preparation 租约于 00:48:02Z 到期。00:49:34Z 数据库绑定已 unknown/disabled/fenced，容器列表为空；宿主状态文件却仍 ACTIVE。安装历史 active 不等于当前可经营。

本波最小修复：`services/aos-api/aos_api/extension_runtime/live_installation_owner.py` 在每次有 PreparedJob 的轮询中先检查真实健康，再消费 verify/enable。检查失败遵循原任务清理路径，禁止继续控制。`scripts/a0v_ecommerce_runtime_host.py` 错误证据增加纯代码位置（文件、函数、行号），不写异常正文、局部变量或凭据。针对性测试覆盖无待处理事件时失去资源、失败后不启用、取消/停止仍正确等待。

持续经营方案尚待落地：把准备期限与运行租约分开；仅独占宿主、exact generation、当前授权与新鲜健康可续短租约；过期不得复活原资源身份；重启须创建新 generation 并验证，再恢复配置与受控启用。不得简单改大 300 秒。已激活但失去资源的安装要通过正式 runtime recovery 完成接续，不能复用只允许 applied 的 preparation reset。

下一步：先修复宿主误报并归档到期事实；再设计并验证运行租约、active 安装恢复和最终业务链衔接。外部发布、230 L0 和 push 均未启用。

状态误报修复完成：有任务的空闲轮询先 check_health，29 项 owner/scheduler/取消/清理测试通过。旧宿主 PID 38645 已有序停止，状态记录 SAFE_BLOCKED/TimeoutError；未拉起新宿主冒充资源恢复。当前真实读回见 ecommerce-1.6-owner-expired.json。AR2-7 闭包检查通过。

后续续租细则：准备阶段仍最多 300 秒；仅成功 verify 的原 owner 能申请短续租。每次续租先真实健康检查，再在同一事务锁 Installation、操作、绑定、资源，核对当前权限、签名发布、exact generation、全部未到期且未释放，才能延长资源租约。DB 提交后才重设进程内计时器。过期或取消时不能复活，清理仍使绑定 unknown/fenced。新续租方法需覆盖未 verify、到期、权限撤回、generation 变化、DB 失败、取消中的提交与清理；落库证明与进程内期限必须同源。

续租实现检查点：新增 `extension_runtime/lease_renewal.py`，原 owner 经健康和 durable expiry 成功后重设计时器；PreparedJob 仅成功 verify 后每 60 秒续约 180 秒。43 项单元/异步回归测试通过，包括权限拒绝、unknown binding、条件失效、提交时过期、资源集合漂移、未 verify 和已关闭 owner 拒绝。当前仍缺真实 PostgreSQL + OCI 超过初始五分钟的连续观测，不能标为长期运行完成。已到期 active@7 不可用续租复活；下一项需正式 active runtime recovery 或规范卸载重装。

第 5/6 步发现：ar2_018 的 active uninstall 固定要求 exact disable/detach 与 activation 外键；已验证但从未配置/启用的安装没有这种历史，无法规范卸载。下一波 1/6 明确 never-enabled 分支：当前禁用/unknown、config_ref=null、无 enable/dispatch/cutover/业务执行历史、全部资源已释放和零未决义务，建立独立真实终结回执；不伪造 activation/disable。2/6 数据库/服务约束设计；3/6 负向及 PG 测试；4/6 真实卸载重装；5/6 同宿主续租跨五分钟及撤权/到期拒绝；6/6 配置启用前置与下一波业务链。若选择 runtime recovery，亦须独立新 generation 及权威回执，不覆盖旧资源。

## never-enabled 卸载实现方案

新增 `services/aos-api/alembic/versions/a0v_019_never_enabled_retirement.py`：既有 immutable uninstall Receipt 增加 retirement_kind，历史默认 detached；仅 never_enabled 类型允许 disable/activation 为空，detached 仍两者非空并保留外键。不伪造曾启用事件。既有 SECURITY DEFINER 函数在禁用/unknown/fenced 检查后增加严格分支：config_ref=null、无配置和 enable/disable 操作历史、无 cutover/dispatch/occurrence/runtime execution、无未决操作、全部资源 released且数量非零。保持原当前安装 CAS、非特权会话、Receipt 哈希、终结一致性触发器。

新维护脚本 `scripts/a0v_ecommerce_never_enabled_retire.py` 使用既有 web 受限身份和 InstallationService.uninstall，同键回放；不直接改状态。测试核对分支必要条件和历史 detached 约束，并在真实隔离库事务中逐项注入可回滚负例验证拒绝；数据库备份后执行真实卸载。随后新 Installation 重装，保留旧实例全历史。未跨五分钟真实运行之前不得宣称续租验收完成。

权限核查修正：宿主 web 身份没有 aos_app 成员权，原设计不能用于安装管理。保留其隔离，新建专用 `aos_a0v_installation_20260912` LOGIN/NOINHERIT/NOSUPERUSER/NOBYPASSRLS，仅成员 aos_app。密码仅保存在隔离恢复目录 0600 文件；连接后明确 SET ROLE aos_app。不授予 runtime/directory 或改动已有身份。首次真实测试被权限拒绝，尚未卸载，负向断言改为精确业务错误码以排除权限假阳性。

七项 PostgreSQL 回滚验收已通过；正式服务发现 `asset_registry/tenant_transaction.py` 强制把已经采用的 aos_app 改成 aos_runtime，与仅授予 aos_app 的卸载函数冲突。最小修复：对当前角色 aos_runtime 或 aos_app 均仅设置 TenantScope，其他角色保持原采用流程。aos_app 已有资产表权限和 RLS；不额外授予账号 aos_runtime，不改业务授权。新增角色保留及租户绑定测试后继续正式卸载。

真实卸载完成：7 项 PostgreSQL 正负例（全部回滚）及 6 项角色/卸载回归通过。数据库备份 4,623,846 bytes，SHA256 954342a91672bf001eec764e5c81ad5a46d031ea5f61c9dcc8dc3b5fedfe7900。a0v_019 正式服务调用后安装 uninstalled@8，首次 replay=false、第二次=true，见 ecommerce-never-enabled-retire.json。重装使用独立 state/ecommerce-1.6-reinstall.json 和幂等前缀；必须读回此前实例 uninstalled，保留所有旧状态文件。

新安装 efc4e640-1b15-403f-9d06-4c6d1a5330a7 已 active@5，generation 7b3ebc06-6340-4462-b07d-1476d2a1fb17。独立 Host PID 41365；`scripts/a0v_ecommerce_continuity_observe.py` 仅读取资源租约、续租事件和逐容器真实 Running，不续租、不调用业务。原始期限 2026-09-12T01:20:49.777917Z，跨期限观测后归档。

下一波依赖：当前 Provider healthy=0、六个 AgentInstance=provisioning、37 skills=evaluated、0 published/frozen plan。先在 `scripts/a0v_real_text_provider_health.py` 加入显式新 attempt 标识，默认旧标识/旧日志路径保持兼容；每个标识独立一次调用，已消耗或未知结果禁止重发。刷新既有 agnes-2.5-flash 的元数据健康证据，然后推进正式 Skill 发布、绑定和责任计划；不把历史健康时间改成当前。
