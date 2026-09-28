# W5CB4 E17-y｜首次预算激活现有账本前置门验证

## 当前实测与方案复审

按 `w5cb4-e17y-formal-budget-producer-transaction-plan-20260928.md` 复习 231-3/5/9 和预算/费用 Store。2026-09-28 18:11 CST 当前签名预检后，`aos_current_preview_20260927@a0v_109` 的 `org-org/dev-project` 在 `conn.read_only=True` 下：Budget Head/Revision/Bucket/Reservation/ReservationBucket、Action Proposal/ApprovalEvent 均为 0；`meta_membership` 只有 `owner:1`。命令退出 0，未读商城源或敏感载荷。这一实例无两名当前正式 maker/checker，也无预算批准。

## RED→最小实现→回归

| 门 | 结果 |
|---|---|
| RED | `AOS_DOTENV_DISABLED=1 ...pytest -q tests/aip/test_aip_budget_activation_exposure_pg.py` 缺模块 `ModuleNotFoundError`，退出 2 |
| 首次 GREEN 修正 | 首跑 2 passed/1 failed：测试将参数非法 `expected_head_version=0` 误期望 HEAD_DRIFT；将陈旧版本改为 2、缺预算版本改为 1，未改产品逻辑 |
| 专项/邻接 | 同命令加 `test_aip_budget_activation_authority.py`、`test_aip_budget_api.py`：24 passed，退出 0；隔离 PG 由 pytest 创建/销毁 |
| 静态 | `compileall` 与 `git diff --check`：退出 0 |

新增 `aip_budget_activation_exposure.py`：在已存在的显式租户事务中核对当前 scope，`FOR SHARE` 锁精确 Draft Budget Head，按同 budgetId 只读计数 CapabilityInvocation、BudgetReservation、daily/pilot Bucket；任一非零、Head 缺失/漂移或租户不符固定禁入。结果对象永远 `external_usage_proven=False`，不把空内部账本冒充已核外部费用。隔离 PG 测试验证空账本、跨租户/陈旧 Head/缺 Head、已有 unknown bucket 拒绝且不修改账本。

## 未完成与下一波

此门只覆盖**第一次**预算激活前的内部账本空状态，不能处理换版时的已有费用，也没有正式预算预览、批准生产者、审批消费或 Budget Receipt。E17-y2 需在不复用业务 Task ImpactPreview 的前提下接持久预览、经当前成员权限核实的独立 checker、真实费用上界和同事务预算激活。当前 API active 422、八类配置 0、Host/worker 关闭、首链 pending；未增加迁移、未写当前库。`browser-pilot` 新截图不可得；旧 Run、dev-org 写、手工 Run、230 L0 不动。
