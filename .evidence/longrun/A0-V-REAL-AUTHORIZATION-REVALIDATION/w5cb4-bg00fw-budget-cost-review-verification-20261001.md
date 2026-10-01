# BG00FW verification — 2026-10-01

## 结论与边界
费用提议审核同事务只读视图、审核/撤销UI、原请求恢复已实现并验证。批准仅历史意见，activationEligible始终false。当前正式库未连接/写/迁/重启，Host/worker/Provider未启动，无商城源/旧12Run/手工Run/230L0操作，无push。当前code a0v125；不将其作为真库版本。正式跨UID/OIDC审核正向、受限consumer预算激活、当前实例安全恢复及自然首链均未完成。Goal未改；防停工仍只方案。

## 基线与实施
m1 e410dec5 / AOS-001037；7强一致CURRENT；memory-validate GREEN1492deliveries/1490tasks/3962events；Task W5CB4-BG00FW-20261001。
- BudgetCostProposalStore.review在同只读RR事务验证current member/original maker or checker及scope，核提议canonical hash、批准checker/source/expiry、撤销原批准/actor。新增GET /cost-proposals/{id}/review，no-store，旧get不改。
- aipBudgetCost.ts严格字段、exact refs、租户/账户/期间/金额/期限关联与eligiblefalse，authoritative GET/unqueued POST。URL仅安全ID/操作/保守attempted，不存JWT/body/reason。
- useBudgetRequestGuard共用epoch、身份、同步busy、防unknown再提交；旧面板最小接入，旧7tests通过。新面板展示具体风险、Provider/model、Owner/checker、期限和历史撤销；无source/身份不符/已有决定/已撤销/unknown均禁提交。

## RED和验证（所有测试DB由conftest创建独立aos_test_*；不是正式业务验收）
1. `.venv/bin/python -m pytest -q tests/aip/test_budget_cost_review_pg.py --tb=short --show-capture=no` 初次exit1：4failed，review缺方法和GET404；实现后4passed/6.62s exit0；追加签发来源漂移与读取失败检查后最终6passed/6.71s exit0。
2. `node apps/web/node_modules/vitest/vitest.mjs run --root apps/web src/pages/s2/BudgetCostReviewPanel.test.tsx` 初次exit1：missing component。实现后与旧面板12passed exit0。追加模型240长度RED exit1后修复。
3. 后端相邻累计命令：`.venv/bin/python -m pytest -q tests/aip/test_budget_cost_review_pg.py tests/aip/test_budget_cost_proposal_pg.py tests/aip/test_budget_cost_issuer_pg.py tests/aip/test_budget_cost_product_pg.py tests/aip/test_budget_cost_client.py tests/aip/test_budget_activation_product_pg.py --tb=short --show-capture=no` → 88passed/49.13s exit0（后追加的2项包含在最终6项专项中）。TLSJWT、PG、issuer历史均真实隔离测试；UI transport stub仅DOM合同，不当业务完成。
4. 前端累计命令：`node apps/web/node_modules/vitest/vitest.mjs run --root apps/web src/pages/s2/BudgetCostReviewPanel.test.tsx src/pages/s2/BudgetActivationReviewPanel.test.tsx src/pages/s2/BudgetRevisionSetupPanel.test.tsx src/pages/s2/CapacityPage.test.ts` → 4files/53passed/575ms exit0。Node路径 /Users/ddt/.nvm/versions/node/v20.20.2/bin/node。
5. `node apps/web/node_modules/typescript/bin/tsc -p apps/web/tsconfig.json --noEmit` → 无输出exit0；compileall两Python实现exit0；git diff --check exit0；services/aos-api/.venv/bin/alembic heads → a0v_125(head) exit0。

## 浏览器现场
Kitewright Skill/engine_adapter SDK，独立8097临时会话，仅本session清理；8434/node59876已监听。实际打开http://127.0.0.1:8434/aip/capacity：新section可见，初始读取/查询/提交3按钮disabled，选择revoke后撤销button disabled。无source输入、无POST批准、无假身份。截图已view_image实际核看；第一张下半部未入镜，追加滚动后完整新面板。下方容量既有读取中/缺少凭证不是正向通过，不对其作业务成功断言。
证据：w5cb4-bg00fw-browser-20261001.json、同名png、w5cb4-bg00fw-browser-detail-20261001.png。

## 下一波BG00FX
预算受限consumer精确读取当前批准/撤销/head/source并同事务active+唯一Receipt；正式OS/OIDC身份、私有配置、当前实例备份克隆安全迁移另波。费用提议创建仍有后端producer，产品发起入口补齐须登记，不得用手工Run代替自然首链。
