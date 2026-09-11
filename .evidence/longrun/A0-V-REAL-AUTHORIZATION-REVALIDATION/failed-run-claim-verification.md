# 原失败运行领取原语验证

2026-09-11，基线6f1dfff0，A0V-FAILED-RUN-CLAIM-20260911。

新增a0v009不可变恢复领取表，保存原失败行/parentHash；scope/run事务锁及run行锁串行化。只有failed、executor_stopped严格true、finished_at非空且原Journal存在可领取。失败事实保存、run切回running与当前绑定验证同事务；不同claim竞争只一个成功，同claim重复返回False且不再领取。当前不调用executor或公开API。

隔离PG Journal组合4通过，含两线程独立连接竞争、来源禁用回滚（零领取记录/仍failed）、退出未知拒绝、重复claim、旧失败事实保留、状态清除停止标记、canary与DELETE/downgrade拒绝。Store仍其他测试部分SQLite，领取事务本身真实PG；run表为最小fixture，非public实际迁移。diff-check通过。

限制：运行线程退出不等于外部请求无效果；此原语只接原Journal恢复，禁止未知请求重新发送。领取后调度执行尚未接线；领取后进程崩溃仍保持running未知，不自动抢占。public未迁移、API未重载，真实首链和八工作台未完成，不push、230 L0挂起。
