# 阶段评审内部异步 service 方案

日期：2026-09-12

基线：`efcade78`

## 合同

新增 `AsyncAnalystStageReviewCommandService`。构造依赖为显式 scoped connection factory、异步 installed runtime invoker、固定 markings。decide 首先在短事务按 target/key 排序加锁并读取同 key StageDecision Receipt；命中则 Owner exact 回读并比对完整 item 与 expectedVersion，零 proof reader、零 IPC返回历史 ref。未命中才装配 composite reader、Owner binding、database phases、one-shot port 和 coordinator。

新发布严格 prepare transaction → 五次 transaction-free IPC → current transaction/publish。未知 IPC、current 漂移、并发 Receipt、取消均不重试。service 无公开 HTTP/worker 入口，不更改 Installation 或租户数据。

## 文件与验收

- 新增 service 与隔离 PostgreSQL 装配测试。
- 新增本 plan/files/verification，更新 closure。
- 验证新发布 exact Store 回读；replay 调用计数 proof=0/IPC=0；replay body/key/version 漂移拒绝；IPC 超时零写。

下一波复核真实 installed invocation factory 与宿主内部调用点；在 1.5.0 可安装版本完成前保持未装配。
