# W5CB4 E17-s3o-w-h｜原 Store 受限发行首个正向切片

基线 `aos-platform/m1@2e8898da`、Authority `AOS-001216`。复习 231-3/4/5/9、栖月汇经营方案、s3o-w-d/e/f/g；D-wave 已登记原 generic/BI/successor/content 受限连接全链。此波先选不依赖正式外部身份的原 `AipProductionContractStore.create_eval_contract` 作为第三类 ProductionContract issuer 原方法切片，证明不止 `_receipt` SQL 标签可写；其余原写者保持下一切片，不能把单方法冒充全链或当前业务成功。

文件级范围仅 `services/aos-api/tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py` 与本波计划/验证。隔离 PG `aos-ar1c-pg:18432` 先用临时 schema 安装原 `aip4_002` EvalSuite、`w2_002` EvalContract、`w2_001` Receipt 表形状，测试登录为非 owner/NOINHERIT、session/current_user 相同；前置只用隔离 suite revision 精确 hash，不虚构当前生产来源。RED 已实测原方法在该登录上因 `aip_eval_suite_revision` 无 SELECT 而失败。随后静态回读发现原 `get_eval_contract` 显式查询 `public.aip_eval_contract_head/revision`，临时 schema 无法完整验证幂等回读。因此 GREEN 应在**同一专用测试容器**中新建一次性独立数据库（绝不连权威卷），于其 `public` 安装上述原迁移表形状，结束后删该一次性测试库和身份；验证真实非 owner 登录和数据库名，再按最小 ACL/RLS/数据库触发器接原 Store 方法。做 create、同键回读、相同幂等键不同输入拒绝、跨租户拒绝与故障回滚；核 Eval head/revision/Receipt 三表精确同一结果。只证隔离原方法，Eval 缺正式 publication/gate 时 readiness 应 BLOCKED，不能宣称可运行。

专项/相邻回归与静态/差异检查后写 verification、m1 精确提交、Task/Delivery、01/06/Prime/D-wave。当前权威库只读，不执行迁移或切换；Host/worker/Provider继续禁入、不 push。
