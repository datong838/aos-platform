# BG00FN 预算产品请求持久恢复方案

基线AOS-001028 / m1@39e6a883，Task W5CB4-BG00FN-20261001。复习231-5§5/6/7、公共产品契约§4/8/11、421、BG00FF持久请求及FL/FM查询。

## 缺口与主线关系
BudgetRevisionSetupPanel仅draft、组件内存持有body且key未保留；没有activation产品表单。FL/FM inquiry须完整原body/key，刷新后不能安全恢复。本波先完成正式预算review产品入口的后端持久原请求合同；BG00FO接现有预算页的预览/复核/撤销表单。旧draft创建本波不改，不能宣称其刷新恢复已修。真实active预算需外部usage权威/原子消费，继续禁入。

## 文件级方案
- 新aip_budget_activation_product.py：独立AOS_BUDGET_REQUEST_DIRECTORY绝对路径、API UID私有0700目录，无默认临时目录/自动创建。复用现有issuer attempt的目录/marker校验（0600、NOFOLLOW、大小4096上限、FIFO拒绝），不接issuer凭据/DB写身份。
- 每次请求重验外部签名OIDC、scope/subject一致、当前owner/admin（原Store还会重验exact maker/checker）。稳定slot=scope+actor+operation+source(ref)。preview source=budgetId/targetRevision/headVersion；decision=previewId；revoke=decisionId；不把可变target/checker/decision/reason加入slot，从而输入漂移不能换key。
- O_EXCL独占写完整原body/版本、身份、hash、确定性key；fsync文件及目录成功后最多调用一次原create_preview/decide/revoke，再复用FL/FM只读查询。已存在slot只查询；同slot不同输入409。持久前失败不能调用写，持久后任何失败保留slot，只读对账；不自动删/覆盖记录，不存token。
- GET只以安全source引用从服务器找原请求，再查PG；不回原body、reason或token。缺slot=not_attempted只表明该产品槽未记录，不表示数据库不存在；残缺/损坏/身份漂移503，绝不能按空处理。历史过期输入仍可恢复查询。
- contracts新增not_attempted/unresolved/conflict结果，复用三种observedDTO；router新增preview-intent、decision-intent、revocation-intent POST/GET，原接口保留，no-store/200/202/409/503。配置缺失503，不能跳过持久保护。
- 新test_budget_activation_product_pg.py：真实PG/TLSJWT原写与原查询；响应丢失后重载/重复POST仅一次、三操作输入漂移、currentmember/tenant/identity、并发、调用前失败、fsync失败/损坏/错权限/软链接/FIFO、实际HTTP无body恢复。故障注入仅验证边界，不算正式业务验收。

## 交付与风险
RED→最小实现→新专项+FL/FM/原budget Store/API相邻累计→复审→verification→m1精确提交→Delivery/CAS/422/D-waves/Prime回读。
无新migration/生产重启/当前真库写，不读商城源、不旧12Run、不手工Run，Host/worker/Provider不启。正式部署必须保存并备份该目录，不能切换空目录绕过历史；恢复一致性/单写者待正式恢复波验证。落槽后调用前崩溃也视unknown，不盲重发；合法无副作用恢复另待产品裁决。
BG00FO接预算review产品表单与安全URL引用恢复，原draft语义不改，禁止localStorage权威及离线写队列。真实身份/外部usage/原子激活/118→123恢复/自然首链继续pending。
