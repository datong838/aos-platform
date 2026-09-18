# OCI unknown cleanup 双标识核对闭包方案

## 1. 问题与目标

- `remove_owned` 返回 false 只表示本次按名称没有观察到可删除对象，不能证明此前 unknown cleanup 的容器已经释放。
- 持久化 journal 同时拥有固定 resource name 与创建后 container ID；只有两个标识分别查询都明确不存在，才可把
  uncertain 结算为 released。
- 任一标识仍存在、查询返回非预期错误、身份格式非法或核对结果非 true，都保持 uncertain；禁止重建、重删或猜测。

## 2. 文件级范围

- `services/aos-api/aos_api/extension_runtime/oci_driver.py`
- `services/aos-api/aos_api/extension_runtime/resource_recovery.py`
- `services/aos-api/tests/extension_runtime/test_oci_driver.py`
- `services/aos-api/tests/extension_runtime/test_resource_recovery_pg.py`

## 3. 不变量

1. `confirm_absent` 只接受既有固定 name/owner/64 位 container ID，逐一执行只读 inspect。
2. 仅 OCI 明确 `No such` 可记为 absent；连接失败、超时、权限错误继续抛出并由 recovery 固定为 uncertain。
3. 任一标识 inspect 到对象即返回 false，不尝试删除；两个都 absent 才返回 true。
4. recovery 仍先在数据库事务中 fence binding 并把 lease 标记 uncertain，退出事务后才访问 OCI；确认 true 后另一个
   tenant-scoped 事务写 released event。既有 advisory lock、防并发和重启恢复顺序不变。

## 4. 验证与退出

- unit 覆盖双 absent、name/container 任一存在、非 No-such 错误与参数拒绝。
- 18432 recovery PG 覆盖 remove false 后 confirm true 结算 released，以及 confirm false/error 保持 uncertain；
  原 fence-first、租户、live lease、重启与并发锁回归继续通过。
- 静态编译、`git diff --check` 与方案一致性复审通过后独立提交；不实际清理当前 OCI，不改变真实运行状态。
