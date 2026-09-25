# W5c6d Store 原事务 opt-in 围栏 API 设计与无效应合同（2026-09-25）

上位 W5c6a–c：真实 Store/metadata 同库同 runtime 身份，但真实 `a0v_094` 缺失；隔离 PG 证实读写 SQLAlchemy Store 自有事务可同事务适配 `OptInHostLease`。`EcomConsistencyStore._apply_batch` 有回执 replay 早返回和新写返回，`update_derived_metrics` 也有 replay/新写双返回。任何 lease 检查若只在入口或仅新写分支，可能在失权时错误承认成功。

## 文件级九步

1. 复习 Store base/strict/retirement/derived API、两类 return、SQLAlchemy `engine.begin()` 退出提交时序与 receipt replay；复习 W5c6c 同事务证据。
2. 本方案先提交。本波仅新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c6d_store_fence_api_design.py` 静态无效应合同及 verification，不改生产 Store/真实 DB/Host。
3. 目标 API：四条 effect 方法接受显式 keyword-only、精确 `OptInHostLease | None`；scope 必须与 command scope 相同。默认 None 维持原路径。Store 自有事务设置 runtime role/GUC 后，调用同事务薄适配器 guard；新写前一次、每个 replay/new-write return 前一次（含 derived），确保提交前失权会回滚。只读 `read_committed_*` 不提交 effect，另列。
4. 合同固定四条 effect API、两组 replay/new-write return 和相对事务位置；目前以设计合同 GREEN，不能把未实现目标误称已生效。
5. W5c5k–z/W5c6a–d 累计结构与隔离 PG 回归；旧 skip/timeout 债如实列，停隔离 PG。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 真实 Store 函数仍缺，不迁移/不接线；评估两次 guard 的 lease renew 锁竞争和长事务过期风险，下波隔离验证。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文和 Prime 独立受管记忆并读回。
9. 下一波 W5c6e：按本设计在 Store effect API 做默认关闭的最小实现与隔离 PG 新写/replay/失权回滚测试；若锁竞争/长事务不满足则冻结回设计。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
