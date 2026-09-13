# D2d-2a 空登记交接表隔离验证

基线16a144ec，迁移租约A0V-CONFIGURATION-STAGE-SCHEMA-20260913，m1单人。新增a0v_036_runtime_configuration_stage.py，前驱a0v_035，Alembic单头a0v_036。仅在18432隔离schema执行；主库未迁移、旧Host未重启。

## 实现

空交接表按租户FORCE RLS、主体和幂等键唯一、原绑定FK。固定来源请求及精确目标不可改；数据库核canonical摘要、禁止夹带字段/浮点目标版本，SQL与Python合同一致。requested仅一次转终态；不可删除/截断/改写终态。当前runtime仅SELECT与五个终态列UPDATE，无INSERT/身份字段UPDATE。

成功须关联原configuration的同scope/install/generation/actor、exact ref、configuration-stage:<requestId>幂等键、相同职责/策略引用及上一版本关系；不能借用其他配置假装本请求成功。来源当前有效性/完整权限仍由后续Host消费者负责；表守卫不授执行权。

## 验证

- 首轮22项隔离PG检查通过。
- 复核发现JSONB目标1.0与1相等，补十进制整数字面量检查及回归。
- 最终test_configuration_stage_schema_pg.py、test_configuration_stage_contracts.py、test_configuration_store_pg.py合计94 passed、7既有warning；24项新表检查、31项请求合同、39项原配置存储回归。
- git diff --check通过；迁移图仅a0v_036，前驱035。

## 限制和下一项

没有API收件入口、限流/主体查询/Host消费者；默认无API权限，不能据此对外提供功能。实际配置/绑定/Case/Run没有变化。下一项D2d-2b完成Host原子登记（成功/拒绝与原配置同事务、当前成员与markings/来源重核、回滚重领），再接受限API与实际浏览器验收。配置登记总流程仍未完成，首链/八工作台不计完成。
