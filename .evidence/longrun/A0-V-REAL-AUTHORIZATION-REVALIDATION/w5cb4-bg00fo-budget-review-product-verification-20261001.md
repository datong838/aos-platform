# BG00FO verification · 2026-10-01

基线AOS-001029 / m1@2d035691；Task W5CB4-BG00FO-20261001。

## RED/修复/新鲜验证
- 后端新专项RED4failed/5.13s/exit1，get_candidate/get_decision_review与路由未实现。
- 前端RED模块无法解析BudgetActivationReviewPanel，1failed suite/453ms/exit1；实现后首批6tests passed（含原draft3项）。
- 首次后端累计61passed/1failed/45.22s：测试直接比较Z和+00:00时间表示，按HTTP DTO序列化规范比较后62passed/47.00s/exit0；没有改业务时间语义。
- 首次tsc exit2：新测试unused import、可选tenant.subject传includes类型错误；补测试使用/明确字符串检查后exit0。
- 复审补异步身份切换中途截断，避免旧来源返回后继续更新URL/发查询；补原预览GET no-store，并复验。

最终后端：
```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_budget_activation_review_reads_pg.py services/aos-api/tests/aip/test_budget_activation_product_pg.py services/aos-api/tests/aip/test_budget_review_inquiry_pg.py services/aos-api/tests/aip/test_budget_preview_inquiry_pg.py services/aos-api/tests/aip/test_aip_budget_activation_store_pg.py services/aos-api/tests/aip/test_aip_budget_api.py --tb=short --show-capture=no
```
62passed/45.94s/exit0，含新4项真实隔离PG/TLS-JWT HTTP，7既有warning。

最终前端：
```sh
/Users/ddt/.nvm/versions/node/v20.20.2/bin/node apps/web/node_modules/vitest/vitest.mjs run --root apps/web src/pages/s2/BudgetActivationReviewPanel.test.tsx src/pages/s2/BudgetRevisionSetupPanel.test.tsx src/pages/s2/CapacityPage.test.ts src/pages/s2/RuntimeNetworkPolicyPreviewPanel.test.tsx src/components/aip/NetworkProposalCreationPanel.test.tsx
/Users/ddt/.nvm/versions/node/v20.20.2/bin/node apps/web/node_modules/typescript/bin/tsc -p apps/web/tsconfig.json --noEmit
```
5files/55passed/654ms/exit0，含新DOM7项；tsc exit0，git diff --check exit0。

## 浏览器现场
- curl http://127.0.0.1:8434/aip/capacity 返回200；browser-pilot Kitewright仓库SDK、独立8097会话，未手写CDP。
- 实际页面org-org/dev-project显示原预算草稿、新预算审批与恢复区；三个模式选择可见，初始3个按钮disabled。只切模式/读取/截图，无预算提交动作，没有注入假身份或模拟成功。
- JSON：w5cb4-bg00fo-browser-20261001.json；PNG：w5cb4-bg00fo-browser-20261001.png（197913 bytes），已查看截图，区域内容可见无裁切。保存证据断言通过，SDK会话已关闭。
- 本次浏览器只证明页面与空态禁入，不证明正式OIDC、后端新版本部署、预算成功或首链；后端正向仅隔离PG/TLS集成证据。

## 方案/代码复审
1. get_candidate同READ ONLY/repeatable-read/aos_runtime/GUC快照读head+draft，验证payload/hash/tenant/id/revision/lifecycle；服务端构造候选及headVersion，页面不猜版本。get_decision_review核对原decision/preview/hash/checker与revocation、当前maker/checker/member，历史批准不是激活权限。
2. 新API DTO/前端严格解析字段、金额/时间/引用/false标记；候选/历史详情与inquiry均原权威读取，前端不制造批准或预算。原写Store无更改；get_preview仅新增响应no-store。
3. CapacityPage仅挂载新增预算审批区，旧draft功能不改。先来源和原请求查询，复核选择无默认批准、需当前独立checker及有效预览；撤销先看批准内容且原因必填。无预算激活或Provider按钮。
4. URL仅保存operation/resource/revision/head及保守attempted标记，无金额/原因/令牌；不存localStorage权限，不进离线队列。刷新仅GET恢复，未知/冲突/失败只读查询；本地已尝试后即使not_attempted仍不重发，服务端FN持久槽兜底。
5. busyRef同步防双击；identity epoch、来源身份及中途检查丢弃迟到结果，卸载后不写UI；不同原引用不能静默换成当前版本。DOM测试包括三操作、unknown、不完整/越权形状响应、身份切换、刷新恢复；stub仅UI合同，非正式业务证明。

## 未完成与下一波
无新migration/真实库写/生产重启；代码a0v123，最后live118为旧现场，118→123独立安全恢复仍待。正式AOS_BUDGET_REQUEST_DIRECTORY及外部OIDC未部署验收，原draft刷新恢复仍待，预算外部usage权威/原子激活/八配置Owner/Host/首链未完成。
BG00FP复习预算外部usage权威与最小合法来源，推进首链必要配置；未知请求无副作用裁决和原draft持久恢复保留待办。Host/worker/Provider未启，不读商城源、不旧12Run/手工Run/230 L0，不push。Goal状态未改，看护方案未实施。
