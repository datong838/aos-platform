# 已完成Dataset回执回读验证

2026-09-11，基线2bcc72da，任务A0V-DATASET-RECEIPT-REPLAY-20260911。

finalizer保持当前run/schedule/graph/source绑定和原父/派生Journal哈希校验，优先回读已提交不可变结果；仅首次生成结果时重新对账基础、派生与投影。避免后续正常数据更新使已完成历史结果无法恢复；缺派生Journal仍拒绝。未改变权威写入路径、旧Dataset展示保护和当前禁入行为。

验证：新测试在已完成结果后模拟当前基础检查BASE_RECORD_NOT_CURRENT，修改前1失败3通过；修改后隔离PG Journal/Dataset与Dataset原子事务5通过。确认已完成回读仍得到原结果、不覆盖新Dataset、源禁用仍拒绝；首次pending、Receipt失败回滚、内存失败后恢复既有用例通过。Store仍为SQLite组合且版本变化由替身模拟，不是全PG或真实源更新证明。git diff --check通过。

限制：actual durable executor在finalizer之前仍会执行原基础/派生恢复，故此修复只解决finalizer直接重入边界，实际入口的已完成结果优先选路仍须接入。失败run重新claim、空批以及真实首链/八工作台尚未完成。public未迁移，API未重载，不push，230 L0挂起。
