# 并发投影顺序验证

2026-09-11，基线d6624907，A0V-PROJECTOR-ORDERING-20260911。

project_pending增加tenant scope命名空间hash事务try advisory锁，竞争者只返回pending，不能越过持锁者读取后续事件。锁随事务结束释放，已有deadline循环负责后续尝试。原Outbox顺序和事件hash验证保留。

真实隔离PG并发复现：旧事件领取后在投影前阻塞，新worker修复前projected=1/pending=1（先处理新事件）；新增测试1失败1通过。修复后第二worker projected=0/pending=2，释放旧worker再消费新事件，最终version=2。组合输出14通过4失败：13隔离PG/循环专项与1旧静态检查通过；4旧test_o1r2_projector用默认5433连接失败，无SQL执行，不能称全量绿。diff-check通过。生产无新增表/字段，仅projector事务锁。

边界：正常projector owner之间串行；最小隔离兼容表未含生产触发器。人为锁住单条Outbox导致SKIP LOCKED跳过、跨平台/店铺identity投影等仍需核验。public未迁移、API未重载、真实首链与八工作台未完成。下一波安装迁移/投影兼容表约束，随后产品恢复入口。不push，230 L0挂起。
