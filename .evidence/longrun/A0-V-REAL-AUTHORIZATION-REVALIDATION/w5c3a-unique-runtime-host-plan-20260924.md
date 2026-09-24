# W5c3a 唯一独立 Runtime Host 空载启动方案（2026-09-24）

## 当前与范围

W5c2b `6702dfbd`：DS 已正式 uninstalled；新 successor `ae42f0e5-270a-4b7b-8a82-fd3bfbb925dc` approved/etag3，尚无 binding/operation/PreparedJob。九路 legacy/fenced，12 schedules disabled、attempt/canary0。8080 API 存活，18181 和独立 Host 当前为 0。正式 runtime operation 未终态数0；22 条未投递 outbox 均关联历史已 cancelled/failed 的 enable/verify，不能误记为新业务执行。

本波仅启动现有 `a0v_ecommerce_runtime_host.py` 唯一独立进程，并验证空载 Host/租户/锁/状态，不提交 prepare。使用当前 0600 runtime 身份文件、签名 bundle 根、信任根；业务 workers 必须在 LivePreparedJob=0 时无源调用。12 调度继续关闭，不读商城源，不手工 run_definition。

## 步骤与文件

1. 再读回 predecessor uninstalled/new approved、九路/12 schedule/attempt/canary 与现行角色/签名材料；确认无其他 Host PID，global singleton lock 未持有，旧 terminal outbox 分类与数量固定。
2. 新增 `deploy/dev/com.aos.a0v-w5c3-runtime-host.plist`（非 KeepAlive）与定向测试；program arguments 固定 Python、Host、credential/bundle/trust/status，status/log 在本波私有目录；加载一次 launchd job。任一启动边界未知先按 label/PID/状态只读对账，不盲目重启第二 Host。
3. 连续读回独立 PID、status `RUNTIME_HOST_ACTIVE`/唯一 positive tenant/0 canary、`liveTargets=[]`、8080 health、12 schedule off、attempt0、source runs/source claims/业务 Run 不增加；若旧 terminal outbox 被处理，仅记审计不重发。
4. verification、m1 commit、不 push。下一波 W5c3b 才在 Host 活着的状态下用原 lifecycle Owner 发一个新 successor prepare，并等正式终态/真实 PreparedJob；失败按正式恢复链。

## 停止条件

Host status 非 ACTIVE、PID 不唯一、出现任何正租户 LivePreparedJob/业务执行（准备前）、canary 非零、旧 outbox 引发新 running 操作、或签名/身份漂移时停止，保留安装 approved、调度关闭并查因。禁止 `KeepAlive` 自动复活或 API 内嵌 Host。
