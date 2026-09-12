# 受控原批次投影验证

基线 f90db51e，m1 单写者，2026-09-12。主 A0-V Lease 内实施。

新增 pipeline_controlled_projection.py，固定 ControlledIngressJournal 的当前绑定及原始、派生完整记录决定事件集合；Receipt 证据逐项匹配 key/hash/revision 并验证实际 payload。与旧投影器共用 projection_order_lock_key。更早范围外 pending 明确阻断，不越序、不代跑；较晚无关事件保留。写入复用原对象和关系函数，提交前再验当前绑定。外层拥有事务提交。

验证：共享锁 helper 缺失的 RED 为 1 failed / 8 passed；实现后 test_controlled_projection_pg.py、test_ec_projection_drain.py、test_o1r2_projector.py 合计 20 passed。专用 18432 PostgreSQL 隔离测试，覆盖双连接锁冲突、数据摘要漂移、遗漏事件、批准失效、写后失效、外层回滚、准确范围及重放。既有 Pydantic/Starlette 警告无新增失败。

边界：测试当前 journal 和 Receipt 读取使用显式 fixture，真实 PG 验证的是行事务与顺序；不代表真实权限或业务首链验收。主库未迁移、P01 未启动、源库未调用。全租户顺序阻塞需独立合法处理前序队列；实际投影身份权限待集成核验。

清册 ar2-7：1803 modules，158 classified，93 migrated，五类错误数组均空；git diff --check 通过。下一波次接完整受控执行与权限核验。
