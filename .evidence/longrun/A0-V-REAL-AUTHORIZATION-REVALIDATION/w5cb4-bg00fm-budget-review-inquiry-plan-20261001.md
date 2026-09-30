# BG00FM 预算决定/撤销只读对账

基线AOS-001027/m1@2ca78ed1；Task W5CB4-BG00FM-20261001。复习231-5审批/恢复、公共产品契约§4/8、420与原decide/revoke。

## 合同
原decision请求hash绑定previewId+decision+checker；原revoke绑定decisionId+reason+actor。两种写操作均同事务追加immutable Receipt，但无原key查询入口。新增只读查询仍要求当前原actor成员；同scope/operation/key/actor找Receipt，原请求hash一致，再验返回对象及关联preview/decision/hash来源。查到历史批准不等于当前有效、未撤销或预算可激活；activationEligible始终false。缺行unresolved，不是重发许可；不同请求或引用漂移conflict；DB异常503。

## 文件级计划
1. aip_budget_activation_store.py：提纯原decision/revoke request hash helper供写/读共用，原写合同不变；抽取上一波只读连接身份检查复用，不改变其条件。新增inquire_decision/inquire_revocation与内部受限两operation查询，READ ONLY/repeatable-read/aos_runtime/GUC/current member，SELECT only。历史决定/撤销引用严格关联同租户preview，检查target/preview hashes/原角色。
2. aip_budget_activation_contracts.py：observed decisionId/revocationId结果DTO，复用unresolved/conflict，只回最小引用和activationEligible false。
3. routers/aip_budgets.py：/activation-previews/{preview_id}/decisions/inquiry及/activation-decisions/{decision_id}/revoke/inquiry，复用原body/key/require_principal，POST只读查询/no-store/202/200/409/503，保留原认证拒绝。
4. tests/aip/test_budget_review_inquiry_pg.py：实际隔离PG原响应找回、原输入/引用漂移、otheractor/跨scope/成员撤销、批准后已撤销仍只是历史、readonly身份/异常503；真实TLS/JWT HTTP原actor链，计数无新增。无mock Store业务验收。

## 验证/下一波
RED→最小实现→专项及预算activation/store/API/preview inquiry相邻累计→review→verification/精确提交/Delivery/CAS/421/D-waves。无新迁移/生产写/重启/UI改动，不读商城源、不旧12Run、不手工Run，Host/worker/Provider禁入。
BG00FN复习预算配置产品入口与服务端原请求保留，接正式身份/unknown只读恢复的最小产品链；不得使用localStorage权威、离线写队列或刷新后新key重发。外部usage authority/active预算/真实首链仍pending，当前真库只读，118到123安全恢复另波。
