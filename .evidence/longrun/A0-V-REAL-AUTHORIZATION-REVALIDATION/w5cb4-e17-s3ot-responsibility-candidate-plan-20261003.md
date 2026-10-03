# W5CB4 E17-s3o-t｜原职责计划冻结到八配置候选读者

日期：2026-10-03。前置复习：231 长程方案、栖月汇产品授权分层、E17-s3i 配置读者验证、原 `AipProductionContractStore` 创建/冻结与 `runtime_configuration_candidates`。本波仅补原链隔离集成证明，不改生产查询语义，不写当前真实库。

## 文件级最小范围

- `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py`：在既有原服务成功冻结职责计划的位置读取候选基线与结果；验证 `org-org/dev-project` 的 `responsibility_plans` 恰增加 1、另外七类不变，异租户候选不变，并独立读回 `responsibility_plan.freeze` 原 Receipt。
- 本计划与同名前缀 verification：保存命令、退出码和限制；D-waves、01/06、Prime 在本波收口时同步。

## 判据与边界

1. 先运行聚焦原测试作为基线；新增断言后运行 ACCEPT 分支与相邻读者测试。RETURN 分支长期 `REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED` 仍须如实保留，不通过跳过或测试占位洗绿。
2. 使用既有 `disposable_database()` 的隔离克隆；原服务创建/冻结，不直接插职责计划或回执；只读检查当前真实库。
3. 这是候选发现证据，不证明同一安装八类相容、当前正式签名来源、Host 身份、自然首链。若测试库或原冻结前提不可用，保留失败记录，不改生产门禁。
