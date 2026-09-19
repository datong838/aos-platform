# AP 失败退休与 Runtime Host 重载方案

## 上位事实

AP definition 已 rev63 disabled；两笔 attempt 分别为 failed 与 abandoned；12 个 Run 与 12 个 Dataset Receipt
保留，Store/retirement/projection 均为零。AP installation head etag5 active，runtime binding rev6 epoch3 ready，
九路由 revision99/group126 指向 AP，三项资源仍 live。qcursor 已停止，无 pending runtime operation。

Runtime Host PID 59258 启动早于严格 Store 修复 `b287ccbb`，必须在 successor 之前受控重载。

## 文件级清单

1. `scripts/a0v_ap_failed_retirement.py`
   - preflight 精确锁定 AP head/binding/definition、双 attempt、十二 Run、零 Store 副作用；
   - 通过正式 disable Owner 接收并处理一次 disable delivery；
   - 验证 binding rev8/epoch4 fenced disabled、九路由回 legacy revision101/group128、三资源 released；
   - 不改变 snapshot Run，不调用 definition，不创建 successor。
2. `services/aos-api/tests/extension_runtime/test_a0v_ap_failed_retirement.py`
   - 固化 exact identity、单 delivery、路由/资源/Store/tenant 边界和无手工执行约束。
3. `ap-failed-retirement-runtime-reload-verification-20260919.md`
   - 记录退休 lifecycle Receipt、Host 旧/新 PID 与启动时间、代码 hash、健康状态和浏览器验收。

## 执行与停止规则

按 `preflight → request-disable → process-disable → audit` 串行执行。任一 current authority、attempt、Store、路由、
资源或 canary 漂移立即停止；已有 intent 时只读对账，绝不重复发送。退休完成后使用现有 LaunchAgent kickstart
Runtime Host，要求新 PID 与启动时间晚于 `b287ccbb`，且启动状态 `RUNTIME_HOST_ACTIVE`、tenantCount=1、canary=0。

本波完成条件是 AP 正式 detached、九路由 legacy、三资源 released、无 pending/unknown，Runtime Host 已加载当前
Store 文件 hash。下一波才允许准备 AQ direct successor。
