# 价格贡献辅助 GET 初始只读审计

基线：m1/f1a1f51，Authority AOS-002032；本线程唯一m1写者。已登记Task qyh-price-contribution-read-admission-20261015，未改业务代码或服务。完整231目标、原用户安装/全恢复授权、每日/每次aos最新同卷PG→API→Web和八台真实场景保留。

## 已读方案及真实源码

产品方案v2/08-价格治理驾驶舱.md；技术方案53-W6-05（包括2026-08-25实施封存）；231串行主计划。router get_price_research_contribution_view → 默认get_ecommerce_workshop_price_research → EcommerceWorkshopPriceResearchService.contribution_view → Store.latest_batch_or_none → connect_read_only。辅助GET仍CatalogDependency；root GET既有ReadCatalog接线不自动授权此路由。

默认Store构造不连接数据库。此读取链只SELECT本库ecommerce_price_research_batch_revision一张表，不调用prepare/freeze/Normalizer，不执行Source/ResearchJob/Provider/通知/调价；db.connect_read_only明确REPEATABLE_READ READ ONLY。结论只适用于此默认调用链，不扩展为所有Store方法或price/customer辅助GET都安全。

## 不能直接换Catalog的原因

1. latest_batch_or_none仅SELECT authority_data，ORDER BY created_at DESC,revision DESC LIMIT1；相同时间/版本跨batch不确定。没有选取外层org/project/batch_id/revision/content_hash/created_at进行行内外一致校验，也无SQL octet_length/CASE读取前字节门。
2. 原BatchRevision验证tenant和items≤100、零效果计数、ledger总和；未验证每项哈希重算、按disposition的台账计数、原prepare请求exact_refs完整种类/原子Skill顺序/Logic身份及item目标唯一性。读取不能仅靠原model_validate宣布完整性通过。
3. prepared生产hash由原PreparePriceResearchBatchRequest JSON加itemHashes计算；frozen生产hash只包含prior/exactRefs/lifecycle，不能误用整个响应JSON的hash，也不能仅校验frozen短hash却遗漏其继承items被篡改。需按原producer逐状态证明，必要时同只读事务读取exact前版并核继承事实；stale模型允许但此producer未见写入分支，必须继续核对合法来源，不能猜算法。
4. createdAt与DB transaction_timestamp需一致截止验证；未来坏行不能通过WHERE时间过滤隐藏为无批次。createdBy/reasonCodes/Ref字符串可能有隐私，原Store无输出隐私门；不能先修改签名载荷再声称原hash成立。
5. contribution_view直接创建默认allowedCommands PREPARE/FREEZE，authority不可读异常也回同默认命令。installed读取只能投影保存事实，必须显式[]，externalEffectsAllowed false，不升级运行/预算/审批/能力状态。缺表或SQL错误应稳定失败，不伪装可信空批次。

## 前端传递边界（仅审计，未登记施工）

当前parsePriceResearchContributionView允许空命令，类型是两命令枚举数组；不像旧达人闭环固定补四命令。但非空批次parser仍要原子Skill/Logic且忽略items详情，因此后端完整性不能依赖它。后续必须用实际正式SDK验收，不能仅rawGET200。

PriceGovernancePage当前Promise.all辅助读catch→null，unavailableContribution填两命令、null批次并显示外部效果0/ResearchJob0；这把辅助读取失败混同可信空态，属于需要另登记UI范围的缺口，不能在本routerTask隐性修改。已有价格高筛选按钮P1也保留；适用UI波先完善方案和Lease，按原稿1280/1440/1920同态比对。真实计数未知不能填演示数字或假0。

## 下一具体施工入口

先补合法producer状态、原hash/typed JSON、当前保存批次及继承链范围证据，并写文件级方案、独立Prime方案复审。预计专用只读reader与专项测试必须另登记明确范围，不改原Store/service/producer/sharedPOST；rootTask仅路由和read HTTP tests。原正常legacy路径保持。

RED应覆盖可信空/正常原producer prepared+frozen、外层与嵌套租户/身份/时间/hash/ledger/refs/重复目标/隐私、超限SQLCASE、并发一致截止、未来选中坏行、缺表稳定失败、legacy不倒退、installed commands[]及query400/anon401/权限禁入。隔离原w6_005 DDL的真实PG验证RLS/write25006/并发快照，fixture不作真人审批。精确冻结代码累计/独立review后才能更新只读API并做原650不变/正式OIDC SDK/三视口现场验收；不读商城源、不写原数据、不开放Provider。

当前只完成默认调用链及缺口审计，不宣称路由接通、完整安全证明、视觉或经营闭环完成。价格dispositions/closure、客户辅助GET、fullC最终真预算/原部署、自然首链、安装全生命周期及观察发布全部继续。
