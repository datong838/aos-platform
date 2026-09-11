# 已安装运行时 live owner 一次调用方案

日期：2026-09-12

基线：`6f5acc3d`

## 审计结论

当前安全 OCI 链已经具备签名制品校验、持久化资源租约、journaled session、声明操作校验和
`PreparationOwner` 生命周期所有权。业务侧尚无可调用入口；`PreparationOwner` 明确禁止 session
对象逃逸，`PreparedJob` 也只暴露 health/verify/enable/stop。若 stage-review service 直接调用
`open_session` 或重新使用同一 resource lease，会绕过 Installation/代际当前性并破坏单一 owner。

## 本波合同

只在现有 live owner 内增加一次调用窄缝：

1. `PreparationOwner.invoke_once` 在 owner 已 prepared、未停止、未清理且 session 索引仍存在时调用；
2. 同一 owner 的调用串行；调用任务在 owner 清理前必须被取消并收敛，异常、超时和取消不重试；
3. `PreparedJob.invoke_selected_once` 只接受其 `PreparationPlan.members` 中唯一匹配的 package id/hash，
   不接受调用方提供 session 或索引；
4. 不公开 session，不新建容器，不读作者目录，不改变 Installation、binding、Registry 或租户数据；
5. 旧 1.4.0 未声明新操作时，由已有 `RuntimeSession.invoke` 的 undeclared-operation 规则拒绝。

## 文件与验收

- 修改 `services/aos-api/aos_api/extension_runtime/preparation_owner.py`。
- 修改 `services/aos-api/aos_api/extension_runtime/preparation_worker.py`。
- 新增 `services/aos-api/tests/extension_runtime/test_live_owner_invocation.py`。
- 新增本波 files/verification，更新 closure manifest。

验证 live session 原位调用、package 唯一绑定、调用串行、失败/取消零重试、stop 收敛；同时回归
preparation owner/worker、persistent supervisor 与 stage-review port。

## 后续边界

本波只补 live owner 能力，不把它描述为 installed authority。下一波增加由 runtime host 持有的 exact
Installation/generation/job directory，并在每次 IPC 前后复核当前 binding/epoch/lock；完成该门后才可
把 `AsyncAnalystStageReviewCommandService` 绑定到真实 invoker。
