# 费用待核算 SQL 状态约束

新增 services/aos-api/alembic/versions/a0v_002_cost_pending.py，接 a0v_001。保持旧 guard 全部身份/hash/revision/时间检查；增加 submitted/unknown→cost_pending，cost_pending→settled，pending 不允许重发或释放。pending 必须有请求/结果/非空唯一用量且 actual=null；后续 settled 不得替换原请求/结果/用量。

迁移只扩展表 CHECK 与原 guard 函数，不迁移现有业务数据，不修改旧迁移文件。降级遇到 cost_pending 必须拒绝，不能隐式抹去待核算事实。

先在隔离恢复库的事务内创建随机测试 schema，构造与 guard 所需列一致的表，执行 upgrade DDL，验证合法与非法转换和身份漂移，最后整笔 rollback。该验证只证明 SQL 状态约束，不是全链迁移验收；暂不对 public 执行升级，Store 接线完成后再做全链隔离迁移。
