# 经营参谋阶段评审已安装运行端口验证

日期：2026-09-12

基线：`5583a8a6`

结论：宿主已具备一次调用、exact 响应、零重试的已安装 review runtime transport；尚未接入同步
StageReviewCommand，也未改变当前 1.4.0 Installation。

## 验证

- 四种 kind 均固定调用 `ecommerce_growth_review_advance` 一次。
- PermissionError、TimeoutError 与 CancelledError 原样抛出且调用计数为一；无本地回退。
- 非 JSON、未知 kind 在 runtime 调用前拒绝；非对象或 extra/different response 拒绝。
- 首次验证因引用不存在的测试路径在收集前退出；更正为实际 `test_ipc.py` 后联合结果为
  `85 passed, 5 skipped`，skipped 为既有环境条件项。
- 编译通过；AR2-7 closure 扫描 1774、分类 136、迁移 93，全部错误数组为空。

## 风险与下一门

同步数据库事务不能直接 await 容器 IPC。下一波先写 transaction prepare → IPC → transaction
commit/revalidate 的方案与状态边界，确保未知结果不重发、current 漂移不发布，再做最小实现。
