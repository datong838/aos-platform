# BG00GE 正式费用配置原子派生

基线AOS-001045/b145a634/a0v127。复习231-5、438与GD证据。仅独立测试库迁移，不连当前真实库，不开Provider/Host/worker。

## 文件级实现与合同
- 新aip_budget_cost_configuration.sql与a0v_128_budget_cost_configuration.py：沿用budget consumer caller/owner。提取原127历史Receipt核验到owner-only helper，原readonly wrapper保持合同。新增派生与readonly查询函数，只接6个原proposal/hash/decision/actor/scope参数。
- 派生price/policy ID由原消费request hash确定；价格数值null，固定development授权由原Provider/model/decision/预算窗口派生，policy引用原BudgetRevision并hardStop/unknown block/不允许zero。原消费Receipt时间提供稳定createdAt。两组head/revision及governance派生Receipt同事务，拒绝残留head/冲突；不更新或覆盖历史。
- 首次派生同issuer advisory锁；current actor/checker资格、未撤销未过期批准、当前budget head及Provider head/内容、预算有效期在写前后核验。重复/readonly查询保留历史，不借历史赋新执行权。
- DB trigger限制active development price/policy及configure Receipt仅精确consumer身份写入；非development、draft/撤回历史仍走原路径。新增5表SELECT/INSERT/tenant RLS到owner，不授予caller表权限，不授予owner任意UPDATE。
- aip_budget_consumer_connection.py/schema manifest精确补新表/函数/trigger；schema差异逐项复核。
- tests/aip/test_budget_cost_configuration_pg.py真实独立caller/PG批准消费后派生、并发/幂等/回滚/撤销和head漂移/readonly历史/直接写拒绝；旧cost runtime夹具price_for明确只在隔离库临时关闭新增price guard以构造不可信历史测试，不能进入生产代码。该夹具不是producer证明。

## 验证/后续
RED缺函数→最小实现→新PG专项+旧consumer/service/process/product/权限manifest+模型治理相邻回归。DB-only无browser。verification/精确提交/Delivery/CAS/439/D-waves。后续BG00GF接有限消费service/IPC原请求，并接模型/Task联合证明，不能以SQL通过冒正式首链。
