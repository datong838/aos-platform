# W5CB4 P2g｜原内容 TaskRun 与预算 held 的完整迁移库子证明

- 基线 `m1@c861ce0a`；仅修改 P2g 计划并新增 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py`。测试使用 `disposable_database`，从已有受管模板克隆一次性数据库，运行正式迁移并在结束时删除该确切测试库；未接入当前业务库。
- RED：新测试最初因缺少 `_seed_original_run_and_budget` 失败。GREEN：公共 `AipTaskStore` 创建 Task、批准两步 Plan、启动原 Run；隔离库显式列名注入正式 BudgetRevision、PriceSnapshot、ActionProposal/Draft/ApprovalEvent 权威，`AipBudgetReservationStore.reserve` 实际生成同一 Task 的 held Reservation。同请求 replay 返回同一 reservation；数据库只有一条对应预算记录，Usage Receipt 为 0。
- 专项 `1 passed, 7 warnings`；内容与通用 EvalRunner 累计 `284 passed, 9 skipped, 7 warnings`；`git diff --check` 通过。纯后端测试 fixture，无前端变化，浏览器验收不适用。
- 此验证**只覆盖 held 预算第一增量**，未有 dispatch、受控 Provider 结果、Provider/Usage Receipt、结算、Artifact、四相 StepRun、正式主体报告和待办候选的同一对象贯通。测试种子是隔离库权威夹具，不是真实栖月汇批准或生产授权；不授权 GET、Issue、Worker、迁移或 Provider 外呼。
- 下一步：沿同一测试库和同一原 Task/Run/Reservation 建立正式 command journal 与当前 runtime receipt，再用受控结果路径完成 Receipt/settlement/Artifact，随后接 StepRun/报告/候选。若正式 dispatch 安装权威无法在隔离库最小形成，记录确切缺口，不用 monkeypatch 冒充全链。
