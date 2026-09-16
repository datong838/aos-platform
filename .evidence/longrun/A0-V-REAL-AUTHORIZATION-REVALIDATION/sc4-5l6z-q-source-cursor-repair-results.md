# SC4-5L6Z-Q｜来源游标所有权修复结果

日期：2026-09-17。结果：`A0V_077_SOURCE_CURSOR_REPAIR_GREEN`。这一步修复的是自然数据链的权威游标，不把已有成功运行、测试绿或 65 行商品数据解释为完整经营闭环。

## 1. 已证实的缺陷与修复

栖月汇商品计划的 Cron 运行 `scr-4eda5462575a4740` 已于 20:00 UTC 成功、写入 65 行且 executor 已停止；20:01 的停用 PATCH 却把进程缓存中的旧手工运行 `scr-bddff0a74c2a4365` 覆盖回 `meta_schedule.last_run`。

现在控制面使用独立的 `persist_schedule_configuration`：冲突更新只写 cron、pipeline、enabled、name 和 ingest，数据库中的 `last_run` 由执行器独占；语句原子 `RETURNING last_run`，API 只发布该权威回读。创建新计划仍沿原入口初始化空游标。租户键、失败时缓存失效和未知写 fail-closed 均保持。

## 2. 历史游标恢复

主库在 advisory lock 内从 `a0v_076` 单步迁移到 `a0v_077`，迁移前后计划行、运行日志哈希均不变。新增修复函数只接受：计划已停用、无 running、当前游标精确等于声明旧运行、目标是同计划最新且已停止的成功运行。修复与不可变 Receipt 同事务提交。

- 修复 Receipt：`6d6b49ea-64e7-4548-8235-84f43a24e52e`
- contentHash：`sha256:2417b909496d2086648f33038f634906350d0c0b486218af37dd9f8b842b40e3`
- 游标从 `scr-bddff0a74c2a4365` 恢复为 `scr-4eda5462575a4740`
- 目标运行：Cron、succeeded、65 行、duration 12453ms、executor stopped
- 同键回放返回同一 Receipt；Receipt 总数 1，负租户 Receipt 0，外部副作用 0。

首次调用后脚本在同一外层连接尝试管理员读回，受 `SET LOCAL ROLE` 影响被拒绝。异常令整个外层事务回滚；全新连接先确认旧游标仍在且 Receipt 为 0，随后才把调用和读回拆成三个连接并使用原幂等键。没有在未知结果下盲目重发。

## 3. 验证

- 配置持久化、真实 PostgreSQL 游标所有权、Scheduler 与 `a0v_077` 正反例：41 passed。
- Data OS 租户写回归：7 passed，2 deselected（仅按本变更选择）。
- `verify_closure.py --phase ar2-7`：1982 Python modules，五类错误均空，dynamic reference errors 0。
- `git diff --check` 与 Python compile 通过。

代码哈希：`data_os_store.py=ad9150b3…`，`wave_ext.py=7241321d…`，迁移 `a1e7fb2e…`，执行器 `4842e654…`。

## 4. 尚未关闭的退出项

该项已由后续运行态验证关闭：18181 已重载并通过真实 PATCH 保持 `scr-4eda…`。下一步进入 Q 新 installation/generation 的安装、配置、登记、启用与首个自然来源窗口；不得复用已卸载 P 的代次和审批。
