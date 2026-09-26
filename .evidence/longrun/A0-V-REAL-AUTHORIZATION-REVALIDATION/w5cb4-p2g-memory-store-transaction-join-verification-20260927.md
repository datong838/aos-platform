# W5CB4 P2g 第十五增量第一切片：AIP 候选事务接入验证

- 基线：`m1@269ac8b8`；本切片仅改 `aip_memory_store.py` 与既有 `test_aip_memory_store.py`，未改候选审批/推广合同、数据库结构或当前实例开关。
- RED：新回滚测试先因缺少 `create_source_revision_in_transaction` 失败。GREEN：来源修订和 pending 候选可加入同一调用方事务，API 不自行 commit；调用方 rollback 后两张权威表均无记录。旧公开接口仍自行 commit/重放，原 AIP 候选测试共 `5 passed`。
- 累计 `tests/extension_runtime/test_ecommerce* tests/aip/test_aip_memory_store.py` 为 `963 passed, 191 skipped, 9 warnings`；跳过不计成功。`compileall` 与 `git diff --check` 通过。直接收集全部 `tests/extension_runtime` 时，历史 `test_a0v_aw_saved_snapshot_recovery.py` 因缺失旧现场 `create-av-result.json` 在 collection 阶段失败，故不将其写成绿色；该历史测试不属于本切片，也未修改其证据。
- 方案一致性：只为第三段反馈的原子候选写入准备事务入口；尚未生成第三段候选、来源/Receipt、ack 或总控回流。当前真实链仍未完成。纯后端且未启当前实例，浏览器验收不适用。
- 风险/下一步：下一切片必须在非超级 Runtime 身份与同一正式迁移隔离库证明第三段 claim、EffectReview exact 来源、AIP pending 候选和 ack 的同事务/独立读回；若 ACL 阻断，不能放宽候选表直接写权限。未知提交不重试，仅只读对账。
