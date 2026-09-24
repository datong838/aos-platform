# W5c3f 失败 Prepare 的只读诊断与正式退休方案（2026-09-24）

## 当前证据

W5c3e `d52d8513`：干净安装 `82ec732b-51d6-4745-a871-57a2cd7848bc` 的唯一 apply `97d921ed-579b-463e-ba2b-0cfccc9d8fb6` 正式 failed/revision7；三个 resource_intent_cancelled，三租约 `create_claimed_at IS NULL`、无 container ID、released/observed；Host PID15014 仍 ACTIVE/空。Docker 隔离及三签名镜像缓存只读检查通过，说明失败位于资源 create claim 之前；具体是 release record/签名 artifact admission 还是更早的 Worker 边界，仍未定位。无 verify、binding、attempt、切流、调度。

## 串行步骤

1. 只读运行与 Host 同配置的原 release-record/artifact admission 校验，但绝不 claim/create/start container，不读取商城源。只报告异常类型和安全代码位置，不输出异常值、机密、artifact 内容；同时核正式 operation/event/lease、业务计数、Host、九路/调度/canary。若无法证明只读，停止该诊断。
2. 若原 admission 通过，继续只读检查 `open_journaled_session` 之前的精确权限/资源信息，不靠重复 apply 定位。需要新观测代码时先最小方案/测试，不让错误文案泄漏包内容或身份。
3. 复用 W5c3c 的正式 approved-uninstall 原 Owner 路径，但用本安装 ID、operation、lock、全新 0600 intent/幂等键 `a0v-w5c3f-retire-failed-prepare-20260924-v1`；提交一次并独立 audit uninstalled/etag4/activeRevision null、历史 operation/租约不变。若边界未知不重发。
4. verification 文档与 m1 commit；下一波修明确原因后，才创建再一个干净 successor；此波不新建、不 prepare/verify/enable、不切九路/调度。

## 停止条件

任一资源不再 released、出现 create claim/container、Host/路由/调度/预算/canary 漂移、原 Owner 拒绝、异常包含不可安全记录内容，冻结并只读对账。禁止将 `PREPARATION_EXECUTION_FAILED` 自身解释成明确根因。
