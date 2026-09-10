# 写前绑定检查验证

2026-09-11，基线1f668ed8。新增save_for_running_schedule共享锁读取当前run/schedule/graph/source后调用save；不读取凭据props。检查running、enabled、live绑定、完整图hash、单一source节点及当前配置UUID/type/status。

新增PG组合先因缺方法红，实现后2项组合通过（含既有不可变journal）。新绑定用最小四表fixture，save在绑定专项中mock，验证有效调用与运行失败/调度关闭/源禁用/图hash和配置UUID漂移时拒绝。fixture授予SELECT/UPDATE以支持FOR SHARE，不证明生产权限；也未证明完整绑定+保存的并发行为。diff --check通过。

锁仅到调用者事务结束；此入口不是执行授权或配置读取前验证，实际executor仍未接入。源props/runtimeMode及pipeline执行配置需在装配环节复验，派生输入还未持久化。public未迁移，API未重载，真实首链未完成，不push，230 L0挂起。
