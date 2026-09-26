# W5CB4 P2f-b 第 2/4 步｜治理/主体 Eval 包隔离正式 API 验证

## 结果

- 新 `ecommerce_content_pre_review_pack.py` 只生成确定性规格，不自动登记。治理 Suite 有完整/空正文/缺事实来源/缺渠道/错 schema 正反 5 例；主体 Suite 仅有一例 `expected=true`。两者 target 为同一审定 Graph exact id/revision/hash，拒绝未经审定的 Graph hash。
- 一次性测试 PG 中，治理 Suite 经正式 Dataset/Suite Registry→EvalRunner→ReleaseGate→Publication；主体 Suite 绑定独立冻结 READY 的 `ecommerce_content` EvalContract。治理报告未冒充内容主体报告；撤销 Publication 后原合同读回 BLOCKED。负租户 `dev-org/dev-project` 无该 Suite/Contract。
- 当前生产实例未注册此 Graph/Suite/Contract，尚无真实 Artifact 主体 Eval，也未绑定新 Plan、启 Worker/Provider 或读商城源；P2f-b 和 W5CB4 均未完成。

## RED→GREEN 与复审

- RED 1：缺少 Eval 包构造模块时 `ModuleNotFoundError`。RED 2：篡改 Graph hash 仍可构造包，预期失败。两处均最小修复。
- 专项＋邻近累计 `59 passed`；`git diff --check` 通过。无 UI 变更，浏览器验收不适用。
- 与 231-5/231-9 一致：这只证明预审结构门可以受控发布；事实、敏感信息、禁用表达等仍由真实人类 exact 决策。下一步做当前权威来源交叉读回、可重入注册预检及 Owner 新 Plan gate；生产迁移未追上时不操作当前业务库。
