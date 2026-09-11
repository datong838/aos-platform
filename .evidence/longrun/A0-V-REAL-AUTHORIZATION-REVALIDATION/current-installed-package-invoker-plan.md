# 当前已安装 package 一次调用门禁方案

日期：2026-09-12

基线：`631dd962`

## 目标合同

新增 `CurrentInstalledPackageInvoker`，构造时固定 TenantScope、installation id、generation、package id、
可信 scoped connection factory、Installation baseline reader、live-job directory 与调用者 markings。

每次调用严格执行：

1. 第一笔短事务锁读 active Installation ref 和指定 generation binding；
2. 复用 canonical Installation store 校验 active lock，要求 binding 的 installation revision/lock hash 与
   active baseline 一致，且 desired=enabled、observed=ready、enabled=true、operationFence=false；
3. active lock 中 package id 必须唯一，调用 markings 必须覆盖 lock target markings；
4. 事务关闭后用 exact TenantScope/Installation/generation 从 live directory 解析 job，并按 package
   id/content hash 调用一次；
5. IPC 返回后第二笔短事务重读完整 snapshot，只有 canonical exact 相等才返回结果。

不在事务中 await，不缓存 admission token，不重试未知结果。第二次读取失败或漂移时丢弃 package 响应。
本波不修改 stage-review service、路由、Installation、Registry 或租户业务数据。

## 文件与验收

- 新增 `services/aos-api/aos_api/extension_runtime/installed_package_invoker.py`。
- 新增 `services/aos-api/tests/extension_runtime/test_installed_package_invoker.py`。
- 新增本波 files/verification，更新 closure manifest。

验收 ready 正向、事务外 IPC、前后漂移、错误 package/marking/binding、目录缺失、异常与取消零重试。
下一波把该 invoker 绑定 `AsyncAnalystStageReviewCommandService` 的工厂，并复核 stage commit 是否还需封印
runtime snapshot。
