# AQ 失败退休、Runtime Host 重载与 AR 继者前置方案

## 上位事实

AQ definition 已 rev66 disabled；唯一 recoverable Store attempt
`16ca3c76-4dbe-48c3-9ff3-4f06eb9fbc82` 为 failed，terminal 为
`RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict`。12 Run 与 12 Dataset Receipt 保留，
Store/retirement/projection 均为零。AQ installation head etag5 active，runtime binding rev6 epoch3 ready，九路由
revision102/group129 指向 AQ，三项资源仍 live。qcursor 已停止，无第二 attempt。

Runtime Host PID 87894 启动早于 strict-link 远端写入批量修复 commit `2ce96305`，AR successor 执行前必须重载。

## 文件级清单

1. `scripts/a0v_aq_failed_retirement.py`
   - preflight 精确锁定 AQ head/binding/definition、单一失败 attempt、十二 Run 与零 Store 副作用；
   - 通过正式 disable Owner 接收并处理一次 disable delivery；
   - 验证 binding rev8/epoch4 fenced disabled、九路由回 legacy revision104/group131、三资源 released；
   - 不改变 snapshot Run，不调用 definition，不创建 successor。
2. `services/aos-api/tests/extension_runtime/test_a0v_aq_failed_retirement.py`
   - 固化 exact identity、单 delivery、路由/资源/Store/tenant 边界和无手工执行约束。
3. `aq-failed-retirement-runtime-reload-verification-20260919.md`
   - 记录 lifecycle Receipt、Host 新 PID/启动时间、代码 hash、健康状态与浏览器边界。

## 执行与停止规则

按 `preflight → request-disable → process-disable → audit` 串行执行。任一 current authority、attempt、Store、路由、
资源或 canary 漂移立即停止；已有 intent 时只读对账，绝不重复发送。退休完成后 kickstart 现有 Runtime Host，
要求新 PID 与启动时间晚于 `2ce96305`，启动状态 active、tenantCount=1、canary=0。

本波退出条件：AQ 正式 detached、九路由 legacy、三资源 released、无 pending/unknown，Runtime Host 加载当前
Store 文件 hash，证据/测试/浏览器复验/提交完成。下一波准备 AR direct successor，转移同一 saved snapshot；
在 AR 权威与新 Host 基线通过前不启动 qcursor。
