# Cutover登记引用兼容契约

2026-09-13T09:36:38.932798+08:00；基线035e55cb。
PrepareRequest/PrepareReceipt加入严格可选registrationReceiptRef；无ref时仅排除该新增键，旧请求的其他None字段不变。准备回执、三处请求重构、激活审批expected payload传播ref。首次登记激活仍在连接前明确拒绝，待当前权限/配置/签名和撤销状态事务接线，不形成中间版本放行。

RED三项失败（原契约拒绝新字段）；初始实现误将ref加入CommitPhaseReceipt，完整回归发现46项拒绝后修正为PrepareReceipt限定。又发现历史重装fixture缺028，已在该单一测试Host校验前加载隔离schema迁移、改用非特权身份并映射函数；其余降级测试不受影响。

最终联合：cutover PG全套+签名生命周期OCI+新ref契约+来源核验，95通过，35.79秒，0跳过，7既有警告。包含旧prepare/pause/commit/finalize/rollback/disable/uninstall/reinstall以及物理OCI释放。AR2清册1819/158/93五类错误为空。主库无部署、无新登记。

下一波抽取并复用登记Owner当前安装/四来源/签名的同事务核验，接入首次prepare来源读取；仍需处理commit期间runtime draining状态和配置漂移、撤销锁序以及主库完整验收。真实首链未完成。
