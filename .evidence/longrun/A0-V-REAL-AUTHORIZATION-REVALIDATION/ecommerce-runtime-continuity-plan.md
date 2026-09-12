# 电商宿主持续运行与故障恢复

2026-09-12。active@7 的首个时点验证通过，但 preparation 租约于 00:48:02Z 到期。00:49:34Z 数据库绑定已 unknown/disabled/fenced，容器列表为空；宿主状态文件却仍 ACTIVE。安装历史 active 不等于当前可经营。

本波最小修复：`services/aos-api/aos_api/extension_runtime/live_installation_owner.py` 在每次有 PreparedJob 的轮询中先检查真实健康，再消费 verify/enable。检查失败遵循原任务清理路径，禁止继续控制。`scripts/a0v_ecommerce_runtime_host.py` 错误证据增加纯代码位置（文件、函数、行号），不写异常正文、局部变量或凭据。针对性测试覆盖无待处理事件时失去资源、失败后不启用、取消/停止仍正确等待。

持续经营方案尚待落地：把准备期限与运行租约分开；仅独占宿主、exact generation、当前授权与新鲜健康可续短租约；过期不得复活原资源身份；重启须创建新 generation 并验证，再恢复配置与受控启用。不得简单改大 300 秒。已激活但失去资源的安装要通过正式 runtime recovery 完成接续，不能复用只允许 applied 的 preparation reset。

下一步：先修复宿主误报并归档到期事实；再设计并验证运行租约、active 安装恢复和最终业务链衔接。外部发布、230 L0 和 push 均未启用。

状态误报修复完成：有任务的空闲轮询先 check_health，29 项 owner/scheduler/取消/清理测试通过。旧宿主 PID 38645 已有序停止，状态记录 SAFE_BLOCKED/TimeoutError；未拉起新宿主冒充资源恢复。当前真实读回见 ecommerce-1.6-owner-expired.json。AR2-7 闭包检查通过。

后续续租细则：准备阶段仍最多 300 秒；仅成功 verify 的原 owner 能申请短续租。每次续租先真实健康检查，再在同一事务锁 Installation、操作、绑定、资源，核对当前权限、签名发布、exact generation、全部未到期且未释放，才能延长资源租约。DB 提交后才重设进程内计时器。过期或取消时不能复活，清理仍使绑定 unknown/fenced。新续租方法需覆盖未 verify、到期、权限撤回、generation 变化、DB 失败、取消中的提交与清理；落库证明与进程内期限必须同源。

续租实现检查点：新增 `extension_runtime/lease_renewal.py`，原 owner 经健康和 durable expiry 成功后重设计时器；PreparedJob 仅成功 verify 后每 60 秒续约 180 秒。43 项单元/异步回归测试通过，包括权限拒绝、unknown binding、条件失效、提交时过期、资源集合漂移、未 verify 和已关闭 owner 拒绝。当前仍缺真实 PostgreSQL + OCI 超过初始五分钟的连续观测，不能标为长期运行完成。已到期 active@7 不可用续租复活；下一项需正式 active runtime recovery 或规范卸载重装。

第 5/6 步发现：ar2_018 的 active uninstall 固定要求 exact disable/detach 与 activation 外键；已验证但从未配置/启用的安装没有这种历史，无法规范卸载。下一波 1/6 明确 never-enabled 分支：当前禁用/unknown、config_ref=null、无 enable/dispatch/cutover/业务执行历史、全部资源已释放和零未决义务，建立独立真实终结回执；不伪造 activation/disable。2/6 数据库/服务约束设计；3/6 负向及 PG 测试；4/6 真实卸载重装；5/6 同宿主续租跨五分钟及撤权/到期拒绝；6/6 配置启用前置与下一波业务链。若选择 runtime recovery，亦须独立新 generation 及权威回执，不覆盖旧资源。
