# AP 唯一自然 recoverable Store attempt 执行方案

## 上位目标与边界

AP 已完成 direct successor、九路由 cutover、definition rev62 与 recovery rev20，strict link 1168 条性能根因
已修复并提交 `b287ccbb`。本波只恢复原 qcursor/API/Snapshot Worker，让 definition 自然领取 AP attempt；
禁止人工 `run_definition`、源重读、未知结果重发和并行 successor。

## 文件级清单

1. `scripts/a0v_ap_attempt_guard.py`
   - attempt 产生后冻结 exact AP identity、request hash、ordinal 与幂等键；
   - 只读核对 heartbeat/Lease、12 Run、Dataset Receipt、relationship/link command/retirement、Store Receipt、
     `ecom_link`、projection pending、resources 与 `dev-org` canary；
   - terminal 前不改变运行态，未知提交边界拒绝自动动作。
2. `scripts/a0v_ap_continuation_router.py`
   - running 只守护；succeeded 只路由 terminal inspect/disable；failed/abandoned 只路由诊断与正式 pause；
   - 不调用 definition、不创建 successor、不重发 Store。
3. 对应 `services/aos-api/tests/extension_runtime/test_a0v_ap_*.py`
   - 覆盖 exact identity、单 attempt、终态分类、Store/Run/tenant fail-closed 与无执行 API。
4. `ap-natural-attempt-verification-20260919.md`
   - 记录服务代码 hash、启动时刻、attempt 演进、业务持久事实、浏览器和终态处置。

## 执行顺序与停止规则

启动前只读确认 definition rev62 enabled、recovery rev20 current、`executionAuthorized=false`、AP binding ready、
qcursor 未加载、Runtime Host 健康、没有 AP attempt。随后 bootstrap 原
`com.aos.qcursor-worker-u` LaunchAgent，等待 18181 健康与唯一自然 attempt。

若出现第二笔并行 attempt、request hash/idempotency 漂移、canary 非零、Store Receipt 与 link/outbox 不一致、
Run 混合终态或服务代码 hash 不匹配，立即停止 qcursor 并只读对账。若 succeeded，执行既有 AP
`inspect → disable`，完成终态证据和提交；若 failed/abandoned，停止领取并进入正式 pause/retire 路径。

本波完成条件是 AP 唯一 attempt 真实成功、12 Run 原子 succeeded、strict link Receipt/ecom_link/outbox/
projection/retirement 一致、definition 正式 disabled、tenant canary 为零。测试通过或服务在线都不等于完成。
