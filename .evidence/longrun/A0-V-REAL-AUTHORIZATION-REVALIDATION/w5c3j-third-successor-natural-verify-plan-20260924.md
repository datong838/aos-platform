# W5c3j 第三个继任者自然 Verify 方案（2026-09-24）

## 目标与时限

W5c3i `238ea348`：安装 `407059df-6f1f-4927-acd7-8e388692838e` applied/etag4；apply `6b668e27-a2ba-4b02-ba2d-d993f389aeda` succeeded；Host PID17302 真实 PreparedJob generation `7571af17-e2bb-4437-9f04-75812bae56c0`、三资源 held。此 Job 有有限 lease，本波立即只走原 `runtime-verify`，不 stage/configure/enable、切九路/调度或业务 Run。

## 串行步骤

1. 复核同 PID ACTIVE/同 generation Job、apply 精确成功、applied/etag4、三资源 pending且未 released、九路/12 schedule/canary/budget 不漂移；全新 verify 键 Command/runtime operation0。
2. 使用 W5c3b 原 lifecycle Owner 的 `request_preparation(kind=runtime-verify)`、全新 0600 intent/result 与幂等键 `a0v-w5c3j-third-successor-verify-20260924-v1` 一次；未知提交边界只读对账，绝不重发。
3. 每50秒只读采样正式 operation 直到 succeeded/failed/cancelled。成功独立 audit active/etag5、唯一 binding 指向精确 generation、disabled/fenced/ready、三资源仍 held、同 PID Job；失败/Host drift/lease released 冻结。
4. verification 文件落盘、m1 commit；下一波才 stage/configure/enable 与九路 route 的正式方案。禁止在本波触发商城源或自然业务 attempt。

## 停止条件

Job、资源、Host、预算、九路、调度、canary 任一漂移；operation 超时/未知或原 Owner 拒绝时停写并正式恢复，绝不手工 verify/伪造 active。
