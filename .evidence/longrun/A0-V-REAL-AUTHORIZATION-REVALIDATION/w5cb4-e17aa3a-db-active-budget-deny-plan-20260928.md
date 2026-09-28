# W5CB4 E17-aa3a｜预算 active 写入数据库层禁入与消费前置门

## 上位与事实

231-3/5 要求当前 Head、精确批准、费用上界和事务内单次消费。E17-aa1 已挡通用 Python Store；E17-aa2 当前价格/用量/外部账单与独立 checker 均不足。`aip10_001` 仍授予 `aos_runtime` 对 `aip_budget_revision` 的 INSERT，故不能以应用守卫声称 DB 层安全。当前 `a0v_110` 且 active 预算为 0，现阶段任何 active 插入都缺合法授权。

## 本切片设计

从 `a0v_110` 单头添加 `a0v_111`：在 `public.aip_budget_revision` 上安装 BEFORE INSERT 行触发器，`NEW.lifecycle='active'` 一律 raise `BUDGET_ACTIVATION_CONSUMPTION_REQUIRED`；Draft 与原其它生命周期不变，既有历史行不更新。函数使用稳定 `search_path=pg_catalog`，不能靠客户端 GUC、伪造 actor 或请求字段解除。禁止 downgrade，以免静默打开旧写入口。

RED 先于迁移：隔离 PG 测试直接以 `aos_runtime` 同租户 INSERT active 必须失败、Head/Revision/Receipt 不增加；Draft 经通用 Store 正向通过；跨租户 RLS 与 append-only 不回退。验证旧相邻测试：只在可销毁库直接造历史 active 的 fixture 必须改为**显式测试权限通道**或先造记录再装 trigger，不能在生产迁移中开后门。不得为了旧测试而给生产角色例外。

## 后续正向架构

E17-aa3b 才新增唯一消费表和 SECURITY DEFINER 原子函数：函数只接受服务端精确引用，在同事务锁 Draft Head、读不可变 preview/批准/撤销/当前双成员/费用来源、对账、单次消费、写 active Revision 与 Receipt；授予最小 EXECUTE，不向普通运行角色开放消费表 INSERT。DB 触发器届时只允许该函数内部可信写，不使用普通角色可设置的 GUC 解锁。当前缺价格和外部账单正式生产者时函数始终 fail-closed，真实实例无正向激活。

本波新迁移先仅在隔离 PG GREEN；代码头高于当前库时不可把最新 API 重启到旧库。当前卷切换另按 E17-z 做新备份、完整恢复克隆、零执行窗口、精确迁移和最新栈回读。文件：`services/aos-api/alembic/versions/a0v_111_budget_active_insert_gate.py`、`tests/aip/test_aip_budget_active_db_gate_pg.py`、现有测试 fixture 最小调整、verification/D-waves/上下文。不得读商城源、启动 Host/Provider、写 `dev-org` 或回放旧 Run。
