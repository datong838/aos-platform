# W5CB4 E17-aa3b0｜完整内容链可销毁克隆测试与最新预算禁入门对齐

## 上位与现状

复习 231 主计划、231-5 首链与预算批准/费用门、E17-aa3a 当前 `a0v_111` 证据。`m1@aa2fb1f1` 的唯一迁移头与权威库均为 `a0v_111`。`tests/extension_runtime/test_ecommerce_content_review_pending_pg.py` 已有 +45 行未提交内容，新增“退回后经正式 ActionProposal/Approval 再生成”的隔离测试断言；本波先读 diff，不丢弃该工作。其 `_upgrade_test_clone_to_head` 调用最新 head 却固定断言 `a0v_106`，八项 PG 测试在业务断言前失败；后续 active 预算测试种子还会被 `a0v_111` 触发器拒绝。

## 文件级最小方案

只改 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py`：
1. 将“升级到当前 head”的固定预期改为当前唯一 `a0v_111`，仍只允许 `a0v_growth_graph_test_*` 可销毁数据库；以当前运行证明 RED 从版本断言推进到 active 直写拒绝。
2. 将历史 active BudgetRevision 仅作为该可销毁库的下游 reader 种子，在同一测试库 owner 事务内暂时停用 `aip_budget_active_insert_guard`、插入后立即恢复。操作前核数据库精确前缀/迁移版本/trigger；任一步异常由事务回滚恢复。生产迁移、运行角色及真实当前库无豁免。Head/Revision 种子与其它测试数据保持原值，不重写业务逻辑。
3. 运行本文件全部 PG 测试与预算直写负例、相邻 Action/预算回归；新增 +45 行断言若继续失败，读完整错误后最小修正，不以旧测试通过掩盖正式身份/费用缺口。

## 验收与风险

GREEN 判据是可销毁完整克隆测试通过、`a0v_111` 运行角色直接 active 仍拒绝、当前真实库只读且 active/绑定为 0。此测试的受控 Provider 和历史 active 种子不构成正式首链，Host/worker/Provider 仍关闭。提交只精确 stage 本文件与本波证据；未跟踪 test-only 现场文件和 Browser 插件工作区差异保持原样。
