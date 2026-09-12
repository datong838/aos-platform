# 调度批准持久关联存储与Owner验证

2026-09-13，基线1a99dbf1，主A0-V Lease。新增a0v_025与PipelineScheduleControlOwner；主库仍024，025仅隔离测试。

新历史表按租户/计划连续版本，绑定exact计划与ControlRef，包含actor、请求hash/内容hash、幂等键与前序；强制RLS、runtime仅SELECT/INSERT，历史更新/删除/清空拒绝。Owner在当前Control锁内锁计划核对live绑定，CAS追加；read_latest只返回关联事实。绑定disabled计划不会启用它。

首次因迁移缺失9项RED。测试旧默认ACL模拟最初误设专用18432/postgres全局默认grant，缺文件时未进入清理；已撤销本测试新增grant，修为只针对随机schema，未接触18435主库。实现迁移后9项通过。Owner缺模块5项RED，实现后14项通过；补并发同请求、不同actor幂等冲突及decode篡改验证，连同原Control Owner共26 passed。两连接并发最终1条绑定。

清册1805/158/93五类错误数组空，diff check通过。fixture当前包资产为明确fake，真实Ledger/CAS/RLS/触发器/事务锁为PG。没有读源/启动计划/写入主库关联。下一切片正式服务/HTTP绑定入口，再接计划运行与恢复，最后025备份演练及部署。
