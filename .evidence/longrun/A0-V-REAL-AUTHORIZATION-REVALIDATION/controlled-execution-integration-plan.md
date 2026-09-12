# 受控执行真实持久层集成

2026-09-12，d1653e4c，主 A0-V Lease。上一波装配路由测试下游为替身，本波在专用 18432 的随机 schema 中移除这些替身。具体文件 services/aos-api/tests/extension_runtime/test_controlled_executor_integration_pg.py。

复用真实 SourceSelection/Control/claim Owner 和原输入 fixture；外部源与已签包资产检查继续明确 fake，仅返回测试店铺。实际 EcomConsistencyStore 使用同一 PG schema、实际 journal/derived/outbox/object/Dataset Receipt，各事务采用非超级用户 aos_runtime。DDL 仅测试 fixture 以独立 owner 创建，运行时不建表。投影 ownership guard 采用现有正式迁移函数；对象、数据集和一致性表强制租户 RLS。

检查一次执行完成到真实 Dataset Receipt；同 run 重放源调用与 Receipt/outbox/object/build 数量不增加；负租户不可读取正租户业务记录。断点场景先在真实投影提交后模拟数据集失败，再恢复原输入，不能再次读源。全流程仍非真实商城业务验收，无主库变更。
