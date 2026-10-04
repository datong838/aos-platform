# b67 文件级方案：受限 evaluator 与 Receipt 配对联合合同

## 已读事实

- 231-3 当前 signed Installation/RuntimeBinding/epoch 才能准入；BIND-1 的组织 Binding 依赖八类 exact ref、新鲜时间窗、租户/版本 CAS/幂等回执。b63 锁序为 Installation→Registry→Binding。
- b22 原型用 Binding 当前事务版本/xmin 与 `capability_binding.evaluate` Receipt 的 operation、resource/result ref 配对；它自身保留可伪造 available 的 strict xfail。b46 原型使用登录仅 EXECUTE、独立 definer 负责 blocked 更新和 Receipt 同事务、重复/错租户/回滚；未计算 signed 八依赖。b66 隔离 Trigger 证明普通 lifecycle issuer 可与可信 definer 身份区分，但没有正式集成。
- 当前权威库 `a0v_135` 只读。唯一136须兼容卸载命令专用角色与既有 shared Receipt command family；本波先 isolated 联合合同，不提前提升代码 migration head。

## 文件与步骤

1. 读取 b22/b46/b66 夹具的 grant、RLS、definer、Trigger 顺序和清理逻辑，在 `services/aos-api/tests/aip/` 建立最小联合测试：普通 issuer 可 create/update，但不可直接 evaluate Receipt；受限 evaluator 登录无 Binding/Receipt DML，只有 EXECUTE；definer 在同事务写 blocked Binding/Receipt，deferred Trigger 对同事务 version/operation/key 唯一配对。
2. RED 必须分别标出缺身份门、缺配对门和独立 Reader 预计算；不能用客户端提供的 GUC/hash/available 作为真实依赖。测试覆盖错租户/错 key、相同 key 相同 hash replay、同 key 异 hash冲突、两份 Receipt、Binding 更新无 Receipt、插入失败全回滚。
3. 若需要修改原 Service/Router，只接入真实受限命令和明确错误，不改变 create/update 或当前生产装配。signed Growth1.13 夹具另验证 Installation/Registry 锁序与撤销/换代竞争；若正式八类来源未齐，结果只可 blocked。

## 完成门与限制

本波只有隔离 signed full-schema 与相邻回归 GREEN 才能称联合合同完成；若仅计划/RED，Delivery 标 checkpoint。正式唯一136与当前实例角色/凭证、备份全恢复零执行窗口另波。Host/worker/Provider继续关闭，无商城源读取、旧Run重放或手工run_definition。
