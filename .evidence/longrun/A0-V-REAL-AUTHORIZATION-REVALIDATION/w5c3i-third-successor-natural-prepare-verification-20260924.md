# W5c3i 第三个继任者自然 Prepare 验证（2026-09-24）

## 结论

**GREEN，仅 Prepare。** installation `407059df-6f1f-4927-acd7-8e388692838e` 的唯一 `runtime-apply` operation `6b668e27-a2ba-4b02-ba2d-d993f389aeda` 经唯一 Host PID17302 自然消费至 `succeeded`/phase succeeded/revision13；安装 applied/etag4、binding0。三个资源 lease 均 pending/`observed_release=false`，同进程 `liveTargets` 有且只有该安装、generation `7571af17-e2bb-4437-9f04-75812bae56c0`、positive tenant。**尚未 verify/active/enabled。**

## 证据

- 方案 `cdfe84f6`；请求前 approved/etag3、无 runtime 对象、全新键0、Host 唯一空载、九路 legacy/fenced、12 schedule off、预算/canary门禁通过。私有 0600 intent/result，新键 `a0v-w5c3i-third-successor-prepare-20260924-v1` 一次请求、`replayed=false`。
- 正式终态直接读回，不靠 accepted/测试推断；`audit` 独立核同 PID/唯一 PreparedJob、apply succeeded、applied/etag4、三 held 资源与精确 generation。定向包装测试 1 passed，`git diff --check` 通过。失败安全诊断未触发；前两次失败根因仍未明确，不能据本次成功倒推原因。
- 九路与 12 schedule 未启用，未读商城源、未手工触发 Run、canary0。

## 下一波 W5c3j（立即）

先方案，趁同进程 PreparedJob/lease 仍有效，用原 lifecycle Owner 全新键单次 `runtime-verify`，50 秒只读采样到正式终态。成功必须 active/etag5、唯一 binding disabled/fenced/ready、三 held 资源和同 PID Job；失败/超时/Host 退出立即冻结、正式 reset/direct successor，不发 enable。
