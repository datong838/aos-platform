# W5c3e 干净继任者自然 Prepare 方案（2026-09-24）

## 目标与严格范围

W5c3d `d454dd92` 安装 `82ec732b-51d6-4745-a871-57a2cd7848bc` approved/etag3、lock `sha256:820eb34977f56544428e3ecde4fbbca637d6a8ad9cdbd66d223cbf35d58f7380`、predecessor null，runtime 空；唯一 Host PID 15014 空载。此波仅对原 `RuntimeLifecycleService.request_preparation(kind=runtime-apply)` 单次发请求，让 Host 自然消费。不得 verify、enable、切九路/调度、手工 run_definition、读取商城源。

## 串行步骤

1. 复用 W5c3b 已测的严格门禁，新增 W5c3e 精确包装脚本：改用 W5c3d result、独立 0600 state、全新键 `a0v-w5c3e-clean-successor-prepare-20260924-v1`；独立核 Host 唯一 ACTIVE/空、安装 ID/lock/etag/资源/operation 空、DS uninstalled、九路 9/9 legacy/fenced、12 schedules off、预算 rev13 有效、canary0、同键 Command/operation0。
2. 写 intent 后仅请求一次，返回独立 Receipt/operation ID；提交边界未知先只读查精确 key/operation，绝不重发。每 50 秒只读采样 operation/安装/Host，直到正式 succeeded/failed/cancelled，观察窗内不提前收笔。
3. 成功只在安装 applied/etag4、三资源 held、同 PID 唯一真实 PreparedJob 指向新安装/精确 generation、九路和调度仍关闭时判绿；失败/Host 退出/租约释放/未知状态判阻断，冻结，不发 verify。验证文档和 m1 commit 后，下一波独立 verify。

## 退出条件

只有单次 request 与完整正式终态审计后收笔；无任何自动重试。Host 环境继续使用 W5c3c 修复后的 Docker PATH，不增加第二 Host。
