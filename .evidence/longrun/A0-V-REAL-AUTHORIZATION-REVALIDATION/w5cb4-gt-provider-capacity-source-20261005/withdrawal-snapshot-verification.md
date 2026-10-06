# 旧SER撤回门实测RED

真实新增2测试：source与allocation均FAILED DID NOT RAISE，2 failed/30 deselected/7 warnings/12.09s。原native_signed_source双签名、原独立批准、真实私有SCRAM SERIAL reader，原runtime直接INSERT并COMMIT；writer独立查询count=1，旧reader后check_native_capacity_supplier_inputs仍通过。

初始启动路径错误发生在shell redirect之前，未运行测试；随后正确目录一次真实测试已终结，不重放未知结果。所有数据在fixture新独立aos_test_*测试库，当前源与恢复副本不改。

方案一致性：现有存在性检查仅对新快照有效；proposal SHARE/FK KEY SHARE不能确保直接withdrawal INSERT的旧SER协调。必须独立withdrawal epoch owner/不可绕过原INSERT trigger/backfill原批准epoch/native锁版本更新，writer-first旧SER拒绝、reader-first实际wait，并审查与原Evidence/Provider/Owner完整锁图。此机制DDL未冻结，当前不编码新迁移。

这是明确未修复缺陷的RED检查点，不是Delivery/完整Source/恢复门/自然首链完成。新增测试保留RED用于下一波修复；不得以测试提交刷新计数宣称研发完成。
