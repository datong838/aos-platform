# E17-s3o-a 并发成员撤销与 Plan 冻结行锁：文件级方案

基线 `aos-platform/m1@3bb69820`、Authority `AOS-001185`，Task `W5CB4-E17-S3O-PLAN-FREEZE-HUMAN-REVOCATION-LOCK-20261003`。先读 231/231-9、49-W6-01、115 exact subject、上波 s3n 与 `AipProductionContractStore` 的 GET、create/revise/freeze/readiness 共用方法；当前真实库 a0v_135 只读、Host/worker/Provider 关闭。

## 问题与证明法

s3n 用 `SELECT 1 FROM meta_membership` 判断真人仍在租户。Plan create/revise/freeze 写事务通过 `_require_responsibility_dependencies` 调用该共用判断，但另一个连接可在判断后、冻结事务提交前删除成员。只读 GET/列表也调用同一个 `_require_exact_assignee_resolution`，不能直接在共用 SQL 加 `FOR SHARE`。

1. 在 `services/aos-api/tests/test_ecommerce_analyst_stage_review_authority.py` 的 `disposable_database()` 创建 org-org/dev-project 正式 Resolver Receipt 与 draft Plan。连接 A 在写事务调用与 freeze 共用的 `_require_responsibility_dependencies`，保持事务开放；连接 B 设置有界 `lock_timeout` 并尝试删除同租户同成员。旧码应删除成功，负例要求 `LockNotAvailable` 因而 RED；新码应在 A 提交前让 B 被行锁挡住。随后 A 经原 freeze 成功、提交，B 再删成员，Plan 只读回读 BLOCKED。另用真正 read-only 的连接 GET 正向确认不因行锁报错；不在真实库写。
2. 最小生产点：给 `_require_exact_assignee_resolution` 增仅供写准入调用的布尔内部参数，默认 `False`。`_require_responsibility_dependencies` 明确传 `True`，只有 HUMAN_PRINCIPAL 成员 SELECT 在这个分支追加 `FOR SHARE`；`_responsibility_blockers` 和其他只读消费者保持无锁，原 Stage Review 已独立锁成员。不得扩大到三类机器 assignee、任意重试或数据库迁移。
3. 跑新负例、原 Analyst 正向、Plan/Resolver 和内容评审相邻串行回归；静态检查和代码/方案复审。若实际并发实验未证明行锁，则不提交“已封闭”结论，改做证据驱动重定位。

隔离测试只证明 Plan 写事务在成员资格检查后的提交窗口有锁；事务开始前或提交后的撤销仍由当前读模型和 Stage 执行门重查。强 issuer ACL、角色/ABAC/容量、机器 Binding 失效及正式首链另波处理。
