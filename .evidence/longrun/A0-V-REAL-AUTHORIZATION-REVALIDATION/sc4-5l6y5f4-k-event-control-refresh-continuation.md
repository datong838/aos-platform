# Y5f4-K 配置刷新后事件控制退场验证

日期：2026-09-16

结论：`EVENT_CONTROL_REFRESH_CONTINUATION_070_GREEN`

## 触发条件

J 代同代次配置接续后，九条业务 dispatch 已到 runtime target（epoch 5、group revision 31），可选事件控制仍保留在 refresh source（epoch 3、group revision 30）。旧 a0v054 要求十路同 epoch、同 group revision，因此在任何写入前拒绝 fence；现场没有半写、重放或外部副作用。

## 方案与实现

- 新增 `a0v_070_event_control_after_configuration_refresh.py`，只替换既有安全定义函数，不新建或改写历史表。
- 未命中 Refresh Receipt 时保留原 expand/fence/shrink 合同。
- fence/shrink 命中最新 Refresh Receipt 时，重新校验 Receipt 的 request/body/hash、租户、installation、generation、group、source epoch、target epoch、target runtime revision、configuration ref，以及 `externalEffectsAllowed=false`、`resumeBusinessRuns=false`。
- 九条业务路径必须精确位于 refresh target 且未围栏；事件控制必须精确位于 refresh source。fence 以组级 CAS 汇合 group revision，只围栏事件控制；shrink 仍按 source epoch 验证 running/claimed/unknown 均为零后删除事件控制。
- Receipt 增加 `configurationRefreshReceiptRef`，保留本次退场所依赖的不可变配置接续来源。

## 验证结果

- PostgreSQL lifecycle/closure 定向回归：24 passed、19 skipped；其中新旧 lifecycle 文件自身为 16 passed。
- 新增负向用例证明任一业务路径 epoch 漂移时零 Receipt、零二次写入。
- Alembic 单 head：`a0v_070`。
- 全新 clone `aos_event_control_refresh_20260916_test`：a0v069 → a0v070，552 张既有表指纹完全一致，主库未提前迁移。
- 主库：新 0600 备份后 a0v069 → a0v070，事务内及提交后 552 张表指纹完全一致；已有 1 条 Refresh Receipt 保留原样。
- 函数 ACL：PUBLIC/runtime 不可执行，只有 maintainer 可执行；SECURITY DEFINER 和固定 search_path 保持不变。
- 本阶段 business writes、source calls、external effects、resumed business runs 均为 0。

## 已知环境检查

扩大回归中的五个 service fixture 在本机 PostgreSQL 5433 因临时 LOGIN role 没有匹配密码而失败，失败发生在连接建立前，与 a0v070 SQL 和状态变更无关；本验证不把该组声明为通过。覆盖 a0v070 的数据库生命周期、不可变 Receipt、排空、租户金丝雀及后续 disable/detach 相容测试均已通过。

## 下一步

使用当前 J 代真实 installation/generation 和既有已禁用事件策略，分别取得独立 R2 审批并执行 event-control fence、drain、shrink；同 key 重放必须返回相同 Receipt。完成后进入九路 runtime disable/detach 与受控恢复，不启动自然经营 Run。
