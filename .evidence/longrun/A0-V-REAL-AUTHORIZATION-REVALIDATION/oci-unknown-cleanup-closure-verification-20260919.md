# OCI unknown cleanup 双标识核对闭包验证

## 1. 实现结果

- `OciDriver.confirm_absent` 对持久化 resource name 和 container ID 逐一只读 inspect。
- 只有两个 inspect 都返回 OCI 明确 `No such` 才返回 true；任一对象存在返回 false，其他引擎错误继续抛出。
- `CleanupOnlyOciDriver` 只透出同一只读确认，没有新增 create/start 接口。
- `ExpiredResourceRecovery` 在原 remove 返回非 true 后才调用确认；true 才进入原 journal released 事务，false/异常
  均保持 uncertain。

## 2. 验证

- OCI driver 与 18432 recovery PostgreSQL：45 passed、1 skipped、7 warnings，5.49s。
  skipped 为需要真实 OCI 的既有 opt-in 用例，未计作通过。
- 新 PG 场景覆盖 remove false 后：双 absent -> released；仍存在 -> uncertain；inspect error -> uncertain。
- cleanup-only、committed cleanup、offline registry cleanup、resource health、session cleanup：47 passed、
  7 warnings，6.55s。
- Python compile、`git diff --check` 与文件边界复审通过。

## 3. 安全结论

- engine 访问仍发生在 fence/uncertain 数据库事务提交之后，不持有数据库事务跨 OCI 调用。
- absent 确认不删除对象、不重试未知删除、不写引擎错误正文；tenant、advisory lock、resource identity 与
  record_cleanup 原约束不变。
- 本波没有访问真实 OCI，也没有改变当前 Host、资源或业务运行态。

## 4. 下一波

在确认无 running attempt 的空窗执行 a0v089 部署器：迁移前备份、旧字段指纹校验、schema/trigger 读回；随后
安全重载 Host/Worker，核对 8434/18181、runtime active/liveTargets0、canary0，再进入 AN direct successor。
