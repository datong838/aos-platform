# W5b1R2 历史 dispatch 判定部分验收（2026-09-24）

## 结果与边界

本波**未完成正式退休**。新 Owner 退休谓词的定向逻辑与主库只读检查通过，但全新 disable 请求在同事务中因 `permission denied for table extension_dispatch_cutover_operation` 回滚。W5b1R2 intent 已冻结，绝不复用同键或重发。旧 enable 仍 `accepted`/未投递/attempt 0；新 disable Command Receipt 0，binding rev11/epoch6 disabled/fenced，12 schedules disabled，activeAttempts/canary 0。

## 已执行

- 对照计划 `f787f26c`，最小修改 `services/aos-api/aos_api/ecommerce_growth_lifecycle.py`：只有唯一 matched activation 且 9/9 legacy、fenced、无安装/代际/epoch、无 claim gate/当前安装 dispatch、历史 lifecycle 全 detached、代际无未终态尝试，才不再重进旧 gate；多个 matched 保持冲突。
- 定向测试 `test_ecommerce_growth_retired_dispatch_gate.py` 与 W5b1 配置测试共 14 passed；`git diff --check` 通过。主库仅调用新谓词，group `6a402d31-83ad-546c-807f-508c87498ce1` 返回 `retired=True`。8080 由原 launchd 服务重启，`/openapi.json` HTTP 200。
- 精确新键 `a0v-w5b1r2-retire-unconsumed-enable-20260924-v1` 的私有 `intent.json` 已以 0600 落盘；`request_disable` 仅调用一次。调用栈在新 `_retired_dispatch_group` 的 `SELECT ... FOR UPDATE` 处被 PostgreSQL 拒绝；`aos_runtime` 仅有该表 SELECT，行锁需 UPDATE 权限。请求事务报错回滚。
- 失败后独立 `preflight` 再次为 GREEN：同一旧 enable accepted/expired、outbox delivered0/attempt0/claimed0、新键 Receipt0、安装/binding/定义/调度/尝试/资源状态均未漂移。

## 测试限制与下一波

数据库集成测试的独立 PG 18434 未启动；25 项相关用例因连接拒绝未执行成功，不将其算作通过。下一波 W5b1R3 先方案、查清 Owner 权限与并发锁语义，修复权限兼容判定并完成回归；使用**又一个全新** intent/键，绝不复用 W5b1R2。若无法证明竞态安全则停在当前 disabled/fenced 状态。
