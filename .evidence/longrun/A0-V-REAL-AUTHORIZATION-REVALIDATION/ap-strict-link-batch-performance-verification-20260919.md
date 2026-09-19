# AP strict link Store 批量化验证

## 结论

AO ordinal-2 的终态 `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict` 是
attempt 300 秒上限的外层分类。结合实时持久事实，实际阻塞位于包含 1168 条关系的
`apply_strict_link_batch()`：对象 Dataset Receipt、relationship assessment 与原 link command 已存在，
但 link Store Receipt、`ecom_link`、link outbox 和 retirement preparation 均为零。

根因是 strict link Store 在同一事务中按端点、按 link 重复执行线性读/锁查询，之后又逐 link 写入和产生
outbox，1168 条 command 形成数千次数据库往返。deadline cancel event 只能在同步 Store 调用返回后被检查，
无法中断该事务内部的逐行循环，所以旧执行会到 300 秒后才回滚。

本波把 strict link 的端点与现有 link 改为按完整复合主键、稳定顺序的批量锁定，并把锁定快照复用于后续
端点校验和 upsert。事务、RLS scope、idempotency request hash、checkpoint CAS、Receipt、outbox、replay
和 retirement 前置条件均未改变；普通 batch 路径保持原实现。

## 验证

- strict link 现有语义加 SQL 次数合同：9 passed；12 条 link 的 ecom endpoint/link SELECT 保持常数级；
- 完整 `test_ecom_consistency_store.py`：64 passed；
- 隔离 PostgreSQL 1168 条 strict link：1 passed，整项含临时 schema、端点装载、单事务提交、精确重放与
  清理为 7.61 秒；终态为 link=1168、Receipt=1、outbox=1168；
- 既有 group link 与 retirement 隔离 PostgreSQL：14 passed / 155.30 秒，覆盖提交应答丢失、投影失败
  回滚、权限撤销、无关事件排序、条件退休与空退休；
- recoverable attempt、AO guard/router、AP saved recovery 与完整 Store 累计：126 passed；
- Python compile 与 `git diff --check` 通过。

一次把 1168 性能主证和既有 PostgreSQL 回归并行启动，两个 pytest 进程在迁移阶段同时 ALTER 全局
`aos_runtime` role，旧回归的 14 项均因 `tuple concurrently updated` 未进入测试体；停止并发后严格串行
重跑，14 项全部通过。该编排错误没有触发产品代码或业务写入。

## 浏览器与运行边界

8434 的“本体管理（数字孪生）”页面仍可加载，显示 AOS v1.6.5、缓存对象与“暂无可见工作台入口”。页面
同时明确显示 aos-api 不可达 / health 500，这是 qcursor/API 18181 按本波停止规则保持关闭的预期状态；
不能把前端可加载称为系统在线。

AP definition rev62 / recovery rev20 保持 enabled 但 `executionAuthorized=false`，qcursor 未加载，未产生 AP
attempt，也没有重发 AO 未知结果。下一波在提交本修复后安全恢复 qcursor，等待唯一自然 AP attempt，按
heartbeat、Lease、12 Run、Store Receipt、relationship/link/retirement、projection 与 canary 连续守护。
