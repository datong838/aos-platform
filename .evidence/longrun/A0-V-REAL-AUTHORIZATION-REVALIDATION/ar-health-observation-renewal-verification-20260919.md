# AR 健康观测续租修复验证（2026-09-19）

## 结果

`HealthObservationStale` 仍是 fail-closed 条件，但瞬时锁竞争现在可在同一活跃 Owner 内重新取得完整资源健康证明并有限重试。最多三次重探、四次提交；上限耗尽后异常继续向上传播，Owner 关闭和资源释放语义不变。

## 真实故障证据

- AR installation：`90e9b84e-225c-4c91-a1d4-7d2751d7c7f2`
- generation：`b41dc281-a6f7-4357-948b-88519e8b8146`
- runtime-apply：`369824f3-c122-4dd3-81f8-aab57fcf3710`
- 07:15:15Z 至 07:23:30Z：10 次 `runtime_lease_renewed` 成功。
- 正常观测到事件落库耗时约 0.3–1.7 秒。
- 下一次两轮事务入口均超过三秒；第二轮 `HealthObservationStale` 由 `PreparationOwner.renew` 向上传播。
- 07:24:43Z：三项资源全部 `released/observed_release=true`；binding rev7 epoch4 为 `enabled=false, operation_fence=true, desired_state=enabled, observed_state=unknown`；AR 没有 execution attempt。

## 修改与安全性

- `preparation_owner.py` 只捕获 `HealthObservationStale`。
- 每次重试前重新运行整个已持有资源组的健康检查，并从可信数据库时钟重新取完成时间。
- stopping、cleaning 或 task done 时立即拒绝重探。
- 权限、条件、当前安装锁、binding CAS、资源 lease 与三秒新鲜度检查均未修改。
- 持久竞争在第四次提交仍失败，不会无限重试或延长失效资源。

## 验证

- Owner/lease 专项：`61 passed, 2 skipped`。
- Worker/installation scheduler/runtime host 累计回归：`69 passed`。
- `py_compile`：通过。
- `git diff --check`：通过。

## 后续

AR generation 不能复活。必须先通过原 disable Owner 正式退休并把九条 dispatch route 恢复为 legacy，再由完整生命周期创建直接后继。
