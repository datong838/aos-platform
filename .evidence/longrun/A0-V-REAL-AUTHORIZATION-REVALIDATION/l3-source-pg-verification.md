# L3来源PostgreSQL组合验证

基线34f0cfe3；专用colima-aos-extension上下文的aos-a0v-recovery-pg已确认运行。使用现有安全container_database_connect_factory在进程内取得连接，未输出凭据。AOS_DOTENV_DISABLED=1、AOS_TEST_USE_SHARED_DATABASE=1、AOS_EXTENSION_PG_TEST=1，执行test_a0v_disclosed_source_pg.py：1 passed（0.30秒测试阶段）。

在fixture随机schema克隆六张public表的结构，显式配置测试tenant RLS。真实Store.resolve写Decision和Receipt，新连接read获取完整payload；原taskId换绑拒绝；dev-org canary不可读取；真实Store.revoke写直接撤销事件后原L3授权拒绝继续读取。未替换Store或policy。fixture只清理自身schema，不改public真实业务数据。

本项验证现有SQL/DTO/Receipt/撤销顺序及隔离测试RLS组合；不证明生产role grant、并发撤销到发送原子性、真实数据映射或八工作台完成。启动旧schema警告及pytest import/deprecation警告仍存在。方案一致，未改产品逻辑，git diff --check通过。

下一步：检查栖月汇现有来源Evidence的字段合同/导航，只输出结构统计不输出正文，再装配可信生成上下文及发送边界；完整首链仍未执行。不push，230 L0挂起。
