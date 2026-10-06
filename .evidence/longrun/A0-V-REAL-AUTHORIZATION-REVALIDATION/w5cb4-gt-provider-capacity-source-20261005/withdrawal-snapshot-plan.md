# 直接撤回与旧SER快照RED
Rules：231/AOS工程交付、原Source Task同Owner显式续租、m1单写。
候选：1 原登记withdrawal epoch writer-first旧SER负门；2 publication独立签名方案。选择首项实际RED，先不编码新DDL。
文件：services/aos-api/tests/aip/test_provider_capacity_source_pg.py；本证据目录withdrawal-snapshot-plan.md/withdrawal-snapshot-red.log。
现有native_signed_source真实test-only双签名和批准fixture，private SCRAM SERIAL reader先固定旧withdrawal快照；另原runtime连接直接INSERT withdrawal并COMMIT（proposal status/version不变），reader再调用原check_native_capacity_supplier_inputs必须拒绝。Source/allocation两target。只在fixture新aos_test_*独立DB，源/恢复副本不动。不用存在性后新事务负门掩盖SER旧快照。若失败，保留真实RED，下一步冻结新增neutral withdrawal epoch owner/ACL/trigger/backfill/锁图后最小修复，不先扩大a151。
