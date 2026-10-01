# BG00FW 费用提议审核与原请求恢复

基线 AOS-001037 / e410dec5；复习231-5 §5/6/7、公共产品契约§3/4/5/8/11/14、430与FV原请求协议。m1单写，真库只读，不启Host/worker/Provider，不读取商城源、不重放旧Run。

## 文件级计划
1. services/aos-api/aos_api/aip_budget_cost_proposal_store.py：新增review只读同事务读取提议、decision、revocation；当前成员且原maker/checker才可读。严格核对decision hash/checker/expiry/source及revocation关联；缺表/漂移不能当未批准。旧get不变。routers/aip_budgets.py增加GET cost-proposals/{id}/review，no-store，无写接口变化。
2. services/aos-api/tests/aip/test_budget_cost_review_pg.py：隔离真实PG/TLS JWT的未审核/批准/拒绝/撤销、当前成员/跨租户、只读与HTTP合同。无正式实例写。
3. apps/web/src/api/aipBudgetActivation.ts：导出既有target parser供复用；apps/web/src/api/aipBudgetCost.ts新增严格提议/审核快照/结果解析与authoritative GET、unqueued POST。每层exact字段，tenant/派生账户/period/限额/provider/ref对应一致；批准始终activationEligible=false。只接受development_risk_proposal。URL只保存proposalId、操作和保守attempted flag，不保存payload/JWT/reason。
4. apps/web/src/pages/s2/useBudgetRequestGuard.ts：从旧面板提取共用epoch/identity/busy/attempted guard；BudgetActivationReviewPanel.tsx最小接入，保留旧行为。新BudgetCostReviewPanel.tsx复用同guard，身份变化丢弃晚响应并清理source；所有提交先读审核快照和原请求，显式checker意见或合法撤销原因。同步busy防双击；unknown后永不换key重发；恢复URL仅GET。审批非激活，展示Provider/model/风险额度/预算/期限/审核人/历史撤销。CapacityPage.tsx仅import与挂载。
5. BudgetCostReviewPanel.test.tsx：DOM/strict parser/URL/unknown/身份变更/恢复/显式决定/撤销保护；模拟transport仅验证UI合同，不能当业务证明。旧面板回归与tsc。浏览器Kitewright独立会话当前页面只读禁入截图，不注入假身份或写真库。

## 验证与风险
先新增RED→最小实现→专项PG/前端→相邻累计→类型检查→浏览器→方案与代码复审→verification/精确commit/Delivery/CAS/431/D-waves/7强一致回读。快照仅审核展示，提交时由issuer重新裁决；历史批准不代表当前授权。真实OS身份与部署、118到125恢复、consumer同事务激活、自然首链均未完成。后继BG00FX优先受限consumer精确批准/撤销/head/source复验与active+唯一Receipt，不以UI替代首链。

复审：模型ID后端max240，前端默认text200造成有效提议被拒；新增240合法/241拒绝RED后精确改为240。审核同REPEATABLE READ/READ ONLY事务，缺表/错误503，source drift409；不会把读取失败映射为无批准。只提取请求guard，不复制安全状态机。浏览器截图补一张滚动后完整新面板，均实际查看。
