# 待核算结算 PostgreSQL 集成验证

新增 services/aos-api/tests/aip/test_a0v_cost_pending_pg.py，复用 test_aip_budget_reservation_pg.py 的随机 schema 与 aos_runtime RLS 连接。原 seed 增加可选 now 参数，默认原值不变，新场景使用当前时间避免过期审批掩盖真实缺陷。

隔离 fixture 中创建明确 deferred price payload 和授权，测试 reserve→submit→实测 UsageReceipt→complete_cost_pending→get/replay。此 fixture 手动放置 active deferred payload 只为提前验证 Store，不是正式 Model Owner 发布证据。验证跨租户拒绝、错误用量回滚、原回执唯一、金额 null、调用状态 completed，以及重复不写入。

连接凭据只在进程内从已验证容器连接取得，禁止放入环境/参数；public schema 不升级，随机 schema 测试后清理。对实际发现的 Store 读写一致性问题最小修复，不放宽授权。
