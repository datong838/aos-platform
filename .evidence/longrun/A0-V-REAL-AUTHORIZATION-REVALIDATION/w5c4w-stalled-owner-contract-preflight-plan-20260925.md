# W5c4w 正式 stalled Owner 合同预检方案（2026-09-25）

上位 231 A0-V、231-9 BG-00；W5c4t 的只读资格仍 `STALLED_WAIT_24H`，W5c4v 的未来错误分类不改变旧失败。本波补正式关闭 Owner 在隔离测试上的请求/角色/严格时间合同预检，**不触发真实关闭**。

## 文件级九步

1. 复习 `pipeline_snapshot_stalled_group_closure.py` 和 `a0v_091` 的 exact request、admin/owner membership、rev4 disabled、12 Run 未起 executor、严格 DB 24h、非业务接受 Receipt 和 effects 保留；对照 231 A0-V 真实接入门。
2. 文件范围：本方案、`services/aos-api/tests/extension_runtime/test_a0v_w5c4w_stalled_owner_contract.py`、本波 verification；不改 Owner/迁移/生产数据。
3. 最小实现：测试 exact Pydantic 请求模型拒绝非 canonical group/key/ref/reason，静态核 SQL 严格 `< clock_timestamp()-interval '24 hours'`、12 条全量、effects evidence、`businessAccepted=false`、唯一 idempotency；若测试需要生产改动，先停止并另写方案。
4. 专项测试：先以缺失测试目标 RED（或契约假设失败）确认测试能检测错误，再跑 GREEN；不得靠伪造真实组通过。
5. 累计回归：隔离库上 W5c4t/v、原 attempt/lease 与 stalled Owner 合同测试；扩展慢集另记，不冒充通过。
6. 浏览器只读：复核 12 单路计划及整组入口；不点运行、保存或冲刷，不能证明后台门禁则 `BROWSER_PARTIAL`。
7. 一致性复审：测试静态合同不等于正式 Owner 对真实组的授权；24h 未到不可调用 Owner；无业务数据读取。
8. verification 落盘提交，再 CAS 同步 AOS 上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c4x：补隔离 PG 的 stalled Owner 实际事务测试与失配拒绝；若 24h 和全门禁已到，可独立写真实收敛方案，一次性调用原 Owner。绝不在本波提前收敛。

停止条件：身份、effect/Receipt、attempt 数、权限或 DB 时间漂移，按原冻结边界；任何未知提交边界不重试。
