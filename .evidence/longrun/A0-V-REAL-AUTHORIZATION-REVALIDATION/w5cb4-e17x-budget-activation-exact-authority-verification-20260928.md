# W5CB4 E17-x｜预算激活精确证据纯合同验证

## 方案/代码复审

复习 231-3/5/9 与 E17-w 后，按本波 plan 只加无数据库纯校验：`aip_budget_activation_authority.py` 绑定精确租户、BudgetRevision 目标 hash/revision、head version、冻结且 ready/用量已知的预算专属预览、maker/checker 不同且 checker 已授权的有效未消费批准及数据库时刻窗口。失败用稳定 code；不读取数据库、不创建审批、不赋运行许可。现有生产 Task ImpactPreview 强制任务/计划等对象，不能直接伪装预算预览；本波证据类型仅为后续正式 Store 事务读取接口的必要条件。

## RED→GREEN

| 门 | 命令/结果 |
|---|---|
| RED | `python -m pytest -q services/aos-api/tests/aip/test_aip_budget_activation_authority.py`：缺模块 `ModuleNotFoundError`，退出 2 |
| 专项 | `AOS_DOTENV_DISABLED=1 ...pytest -q test_aip_budget_activation_authority.py test_aip_budget_api.py`：初次 19 passed，新增畸形 hash/空 checker 负例后随邻接复测，退出 0 |
| 邻接 | 同命令加 `test_aip_budget_contracts.py test_aip_model_governance_policy_contracts.py`：最终 50 passed，退出 0 |
| 静态 | `python -m compileall -q services/aos-api/aos_api/aip_budget_activation_authority.py`、`git diff --check`：退出 0 |

17 个参数化负例涵盖错租户、预算对象/版本/hash、head、预览 hash 漂移/畸形、同人/空白/未授权 checker、撤销/已消费/过期、未冻结、用量未知、金额/窗口变化。正例只证明这些必要条件在人工构造数据中自洽，**不证明**存在当前正式预览/批准、可安全计费或真实业务通过。

## 当前状态与剩余风险

此模块尚无产品调用方，不能将可构造的 evidence dataclass 当数据库权威；下一波必须建立服务端正式生产者、权限/费用只读来源、同事务锁与消费、幂等 Receipt，再让公开 active 入口有条件放行。当前 `aos_current_preview_20260927@a0v_109` 未迁移未写；预算 active HTTP 422、八候选 0、Host/worker/Provider 禁入。若新增迁移使代码头高于当前库，必须另波完成一致备份、克隆全链与零执行窗口后才切换；禁止强启最新 API。`browser-pilot` 不可用，无新截图。本波未读商城源、未碰 dev-org/旧 Run/手工 Run/230 L0。
