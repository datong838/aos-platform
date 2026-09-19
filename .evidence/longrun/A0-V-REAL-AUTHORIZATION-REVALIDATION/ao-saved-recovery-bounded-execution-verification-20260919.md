# AO 保存恢复有界执行与心跳诚实性验证（2026-09-19）

## 结论

本波完成代码级修复，但没有改变当前 AO 运行态。受管 Worker 后续每次保存恢复均获得固定 300 秒 deadline；调用方已有更早 deadline 时保持更早值。AO 只读守卫不再把“心跳与 Lease 健康、运行时间已超过上限、Store 后段零持久事实”称为健康业务推进，而是返回 `RUNNING_HEARTBEAT_ONLY_DIAGNOSE`、`automaticAction=false`，Continuation Router 唯一路由为 `DIAGNOSE_AO_BOUNDED_EXECUTION`。

## 验证证据

- 纯路由/恢复累计：`test_a0v_ao_attempt_guard.py`、`test_a0v_ao_continuation_router.py`、`test_a0v_ao_saved_snapshot_recovery.py` 共 46 passed。
- 隔离 PostgreSQL：`test_snapshot_worker_recovery_pg.py` 新旧五项均取得通过证据，包括默认 300 秒、保留更早 deadline、过期拒绝、disabled 零执行、权限撤销复验。整文件一次运行在第四个夹具建组时跨整分钟，触发既有 `new group requires the current schedule minute`，该项单独复跑 1 passed；这不是产品实现回归，保留为夹具时间敏感风险。
- Python 编译与 `git diff --check` 通过。
- AR2 当前阶段验证器：`verify_closure.py --phase ar2-7` 输出 `scannedPythonModules=1988`、`classifiedModules=200`、`migratedModules=93`，`hashErrors`、正反向未分类依赖、跨层导入、动态引用错误均为空。默认 `ar2-0` 会按早期 preHash 报告后续已提交文件漂移，不作为当前阶段门。
- 浏览器只读验收：`http://127.0.0.1:8434/ontology` 可达，标题为“本体管理（数字孪生） · AOS”，对象列表与图谱健康入口可读；当前身份下电商工作台仍显示“暂无可见工作台入口”，没有因本波后端代码产生越权可见性变化。

## AO 实时边界

实时只读执行保存于 `/tmp/a0v-ao-bounded-live.json`。观测时 attempt revision 220、elapsed 6630 秒；heartbeat 与 Lease 新鲜，control 尚余 14939 秒；十二 Run、十二 Dataset Receipt、一个关系、一个 1168 链接命令不变，Retirement、链接 Store Receipt、`ecom_link`、链接 Outbox 均为零，projection pending=0，三资源有效，`dev-org` canary=0。新结果为：

`RUNNING_HEARTBEAT_ONLY_DIAGNOSE / automaticAction=false / executionLimitExceeded=true / DIAGNOSE_AO_BOUNDED_EXECUTION`

这只证明“业务推进未被持久事实证实”，不证明当前 Store 调用必然未发生，也不授权终止、重发、手工 `run_definition`、退休或 successor。

## 方案一致性与风险

- 复用原 `deadline` 和 `_check_active`，没有新增写 Owner、重试、源读取、Run 或幂等键。
- 300 秒与现有受控 Pipeline 最大执行上限一致；本波未引入外部可调参数，避免调用者扩张执行窗口。
- 当前服务进程未热加载本修复，所以 AO 本次未知执行不会被新 deadline 中断。只有服务按正式恢复流程重载后的后续调用受保护。
- AO attempt 总时长不是单次 Worker 调用的精确计时；守卫只有在 Store 后段完全为零时才给出 heartbeat-only 诊断。若已有部分 Store 事实，则继续交原未知边界对账，不能据总时长推断重试。

## 下一波

立即进入 AO 当前未知边界的终态守护与正式处置方案：继续只读核对 attempt、数据库会话/锁、Store Receipt 与链接事实。若 succeeded，执行既有 inspect/disable；若 failed，冻结未知提交边界并走正式 retire/direct-successor；若继续 heartbeat-only，则完善“停止心跳前的安全失联/控制窗口到期”判定与可恢复宿主重载方案，仍不手工重发。
