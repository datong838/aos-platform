# Agent文本私有存储检查点

2026-09-11，基线9d3b9a29，m1串行，无push，230 L0挂起。

- a0v_012新增tenant/artifact绑定append-only正文表，UTF8 hash CHECK、2MiB边界、FK、强制tenant RLS、no-truncate；PUBLIC无权限。独立于timeline metadata，不新增公开route。
- AipTaskStore可选text_content，与原artifact同事务保存，失败全回滚；显式id重放核验正文，旧缺正文产物拒绝补写。
- executor构造参数retain_output_text严格bool、默认False。默认仍只保留hash/引用；显式启用正文走Owner私有表，不写metadata/attempt/receipt/log。
- Red新模块缺失；新增与executor回归50 passed，随后严格bool回归与增长链累计151 passed，exit0；再补旧artifact无正文拒绝补写，focused19 passed。既有7warnings与退出日志告警未改。
- 一次性完整克隆DB运行upgrade真实DDL（未mock SQL），真实artifact正文保存/重放/read、标记拒绝、跨scope拒绝、RLS错租户0、UPDATE/DELETE/TRUNCATE拒绝、timeline无正文、body insert故障原artifact回滚均通过。未启Provider。
- alembic heads只有a0v_012；只读确认实际主库仍a0v_011，测试DB残留0。此次没有升级主库/长期克隆、没有重启API、没有在业务开启retention。升级时须后续备份与正式migration验收。
- 下一波：GrowthPlan恢复入口读取已保存原正文再走现有接收核验，不允许unknown重新调用。随后迁移部署/业务生成组合显式retention、审批来源重验、真实首链与8场景。
