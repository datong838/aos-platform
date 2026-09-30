# W5CB4 BG00db｜准备态控制命令受理门文件级方案

## 上位复习与缺口

依 231-3 安装先准备/验证、后配置/启用，E16 同进程 Host 受理门，E17 当前签名三身份和 Owner 门。BG00da 准备态 Host 不装配置、启用、停用消费者，却保留 `RuntimeConfigurationService` 的受理入口。当前路由在 `configure/enable/disable` 分支不检查 Host 模式，会产生已受理而本进程无人执行的操作。当前正式实例仍无凭据/assignment，库只读。

## 最小设计

1. `routers/bundle_runtime_installations.py`：仅当当前进程 Host selection 精确为 ACTIVE 且 `preparation_only is True` 时，拒绝非准备控制 `configure/enable/disable`，返回固定 503 与安全中文提示；在调用控制服务前判定，不产生 Receipt/数据库写。`runtime-apply/verify` 保持 E16 当前 Host/assignment 受理门。完整模式和无准备态选择时的历史行为不改。
2. `tests/extension_runtime/test_runtime_installations_api.py`：RED 验证三类命令在准备态全为 503、控制服务调用计数 0；完整模式保持现有 202；准备命令继续走自身准入函数。对错类型或失败 Host selection 不当作可执行正向。
3. `scripts/a0v_current_runtime_host_preflight.py`：准备态不投递已启用绑定的 rehydrate，也不装 disable 消费者。为防止已有启用绑定被遗漏，在准备态预检中只读确认当前租户 enabled binding 为 0，存在则 `ACTIVE_BINDING_REQUIRES_FULL_HOST`；完整模式不加此门。对应 preflight 测试先 RED。对当前实例不启 Host/worker、不写当前库。

## 验证与风险

RED→最小实现→专项/相邻累计、`py_compile`、`git diff --check`、当前正式只读门复核。准备态期间已有完整模式的 accepted 操作可能暂时等待消费者，本波不重发、仅保留查询对账；正式模式切换须另有操作/Receipt 清单和运行窗口。browser-pilot 不可用时不声称浏览器验收。
