# PostgreSQL实际投影器恢复组合

2026-09-11，基线8e8f0f03，A0V-PG-PROJECTOR-COMPOSITION-20260911。

PG恢复组合不再手工标记projected；真实Store基础/派生Outbox由project_until_caught_up消费，验证两事件已投影、一Payment对象、orderId及sourceIdentity，再进入Dataset回执事务及恢复验证。SQLite分支维持旧测试辅助。

首次5通过1失败来自测试误用external_id；核对Store序列化合同externalId后修正断言，未改产品。最终6场景通过，含既有pending/租户隔离专项。diff-check通过。兼容对象表为最小隔离表，不含生产触发器；无真实源，非全安装迁移/实际调度worker验收。

下一波审查并发投影顺序：当前FOR UPDATE SKIP LOCKED允许不同worker处理同对象不同版本，需验证旧版本是否可能最后覆盖新版本。然后安装迁移兼容性和产品恢复入口。public未迁移、API未重载、真实首链和八工作台未完成，不push，230 L0挂起。
