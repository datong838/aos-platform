# W5CB4 E17-f｜预算 active 非 HTTP 写入调用方审计（2026-09-28）

## 范围与方法

只读搜索产品代码与非测试脚本中的 `AipBudgetAuthorityStore`、`.publish` 调用，并逐个读调用上下文。未执行任何历史 bootstrap、配置脚本或当前库写入。上位约束：231-3/231-9，E17-d/e 正式审批缺口与公开 HTTP active 禁入。

## 精确调用方

| 路径 | 观察 | 判定 |
| --- | --- | --- |
| `services/aos-api/aos_api/routers/aip_budgets.py` | 唯一服务端产品代码 `store.publish`，E17-e 已在 active 时调用前拒绝 422 | 当前公开入口失败封闭；draft 保留。 |
| `aip_model_governance_policy_store.py`、`aip_content_draft_readiness.py`、`aip_media_finance_service.py`、`routers/aip_model_runtime.py` | 构造预算 Store 后只用 `get`/精确引用读回 | 这些不是预算修订写入入口。 |
| `scripts/a0v_current_runtime_configuration_authority.py:231` | 直接 publish active，写死预算金额和历史 `approval:AOS-000573:A0-V-local-readonly`；`run` 强制库名 `aos_meta_head`，且 `_inventory` 回读相同 DB 身份 | 对当前 `aos_current_preview_20260927` 的脚本入口已有旧库身份拦截；不可拿历史批准值做当前来源。 |
| `scripts/aip/bootstrap_r1_runtime_authority.py:154` | 直接 publish active，金额来自历史 R1 单，`--apply-prerequisites` 可进 `apply_prerequisites`；未在该函数/CLI 发现当前数据库名与 A1 版本拒绝 | 历史 R1 脚本不应被用作当前 BG-00 生产者；需单独补精确当前库保护或退休标识。 |
| `scripts/aip/execute_r2_*_real_pilot.py` | 引入 Store 但 `.get` 读预算 | 不发布新预算。 |

## 下一文件级切片

1. 先对 `scripts/aip/bootstrap_r1_runtime_authority.py` 建只读目标 DB/阶段负例，当前库 `aos_current_preview_20260927` 必须在任何 Provider/预算/策略/资料写前拒绝；允许的历史隔离用途需明确。需要先读脚本入口及现有测试，再写方案、RED、最小守卫。
2. 正式预算 positive producer仍需要独立 Approval Owner/精确 Receipt：租户、预算 ID/revision/hash、金额、窗口、maker/checker、撤销。现有 ActionApprovalEvent 用于具体 Action 与预算占用，未发现预算配置发布的 ActionType/Proposal；历史 R1 纸面审批不能替代当前批准。
3. 当前库继续只读。八类 active 候选 0，签名、三身份、OCI、Owner/assignment 和浏览器 `browser-pilot` 尚未齐；Host/worker 不启动。

该审计仅依据静态调用图；动态导入/反射和外部直接 SQL 写未纳入覆盖，不能称全系统无其他写路径。
