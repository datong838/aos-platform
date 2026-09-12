# 登记 Owner 强制当前签名资格

2026-09-13，基线 eeef07d2。FirstDispatchRegistrationService 构造必须提供 exact ReleasePolicy；每次 register 在当前安装/四来源预检后，同一 serializable 事务取得当前 baseline，执行签名声明资格检查，核对 schema/lock/package/九项/nonexecutable，之后才采用 maintainer 调用 027。历史读取不新增执行权，也不依赖旧版本签名资格恢复权限。

RED：新增必需 release_policy 测试先在 Owner 构造处失败。GREEN：Owner 实际隔离 PG 编排、资格、预检和回执四组共 61 passed（5.59s），7 项既有警告。配置与资格节点的 pg_backend_pid/txid/current_user 和实际写回执触发器记录相符；缺失/不完整/不同 lock 资格、签名检查抛错、已有预检拒绝及回读异常均无路由/回执残留；幂等重放和历史访问权限行为保持。

07:15 新代码用当前真实主库、aos_runtime、serializable 事务联合当前安装/四来源与签名检查通过。dispatchRows=0/businessWrites=0/registrationExecuted=false。证据 first-dispatch-current-combined-prechecks-v1.json。未采用 maintainer、未执行主库登记、未部署 026/027、未重启 API。

AR2 ar2-7：1816 扫描/158 分类/93 迁移，五类错误为空；diff 检查通过。检查新增签名依赖为必需项，无默认允许、无自动重试、无权限扩大。Owner 的现有生产调用点尚未组装；只有本测试构造点需要更新。

限制：隔离 PG 测试中当前权限和签名资格节点是编排替身；真实主库联合检查证明真实前置条件，但未覆盖“真实完整前置条件+维护身份+正式 HTTP+登记提交”的全链。因此正式 API、维护身份权限审查、首次 fenced 切换、未激活撤销和自然源事件消费者仍待完成。

下一波：正式安装控制平面/HTTP 接入的具体权限与连接方案，完成非特权端到端登记验证；再首次 exact 审批切换、未激活撤销及自然事件首链。继续 m1 串行、不 push，230 L0 挂起。
