# Niushop 1.4 前序实例正式退役

2026-09-12，4c7b74fa。当前a0fd8e25-cb6f-49e5-aa77-7faddae12099在原1.3平台安装上已disabled_committed，绑定unknown/disabled/fenced@7，旧3资源确认释放。新1.4已正式本地注册，但无新安装。

修改 scripts/a0v_ecommerce_never_enabled_retire.py：将已有精确目标选择提为纯函数retirement_target，保留原4路径，增加互斥 second-sleep-1-7 固定a0fd8e25、etag5、新幂等键。对应 tests/extension_runtime/test_a0v_retirement_target.py，验证所有固定目标及旧键不变，无任意UUID入口。脚本继续使用原安装控制身份、InstallationService.uninstall和PG不可变Receipt，不增加授予权限，不手写状态。

执行前只读检查四种调度/调用记录为零、当前配置存在、历史enable/disable精确证明、无未决操作及三资源released。最终权威由既有a0v_021函数持锁再核验：同租户/安装revision、配置ref、单一成功enable/disable事件及payload hash、binding/epoch匹配，任何dispatch/cutover/occurrence/attempt存在或资源未释放即拒绝。前检查不是授权替身。

仅正常uninstall一次并使用相同命令重放回读，要求uninstalled/activeRevision null、runtime uninstall Receipt中的enabled_undispatched、dispatchCount0/businessExecutionCount0/releasedResourceCount3。保留真实商城、数据源、历史业务数据与旧Receipt。失败不绕过Owner，不换key。

下一波固定新平台1.4的schema证明和安装入口，审批组合→apply→verify→配置→启用，Host新根与当前Owner逐步验证；P01仍不通过旧live路径开启。230L0挂起，不push。

执行前验证：先RED6失败，修改后目标与既有uninstall相关12通过。13:33:05Z真实只读预检四类调度/执行记录全0，binding disabled/unknown/fenced@7、epoch5及原configRef一致，详情niushop-1.4-predecessor-retirement-preflight.json。资源释放与原enable/disable终态证据沿前波，最终由原PG函数再持锁核验。
