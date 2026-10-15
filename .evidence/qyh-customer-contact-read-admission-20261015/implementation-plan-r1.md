# 客户联系保存贡献：上位实施方案

基线b9113497/m1、Authority2037，同owner contact parent与maintenance-r10至08UTC；产品v2/09及技术56-W6-08含8/25封板已复习。完整231Goal/原唯一真人授权/daily每次实际aos最新原卷全面PG→API→Web/aos2不重启、原数据只读/HostworkerProviderOFF/unknown旧12不重放/disabledSchedule/source/noPush不变。

## 必需前置：原Start签名材料保存

原producer probe-r1确认：contentHash签名含typed batchRef/exactRefs/items和request.reason，原Start模型却未存reason。直接放行非空读取无法完整验证这个签名。先另Task登记domain/store/专项新test及其E，独立文件方案Prime后只补该签名材料的私有持久化，原签名配方、idempotency hash、公共wire字段和五false不变。新Start可保存原reason；旧Start无reason保持可反序列化且不补写、不猜、不重放，后续reader对选中的不可重建签名稳定拒绝。不能以空视图或弱校验绕过它。

reason采用可选默认None、Field(exclude=True,repr=False)作为旧记录兼容的私有签名材料。原start_batch在任何reservation之前核理由不含public redact_sensitive可识别敏感值，稳定拒绝而不echo；新Start构造传入原request.reason。Store只对Start authority_data显式保存reason，public model_dump/API及frontend exact parser保持原字段；type model_validate回读私有reason。原生产start/actionReceipt resolver恒拒绝，不解除。新增canonical私有authority serializer纯函数供Store/后续reader复用；它只还原原记录，不新增授权或重算签名算法。

## 后续专用reader与路由

前置代码合同经独立复审/冻结/原DDL隔离PG后，再另Task登记ecommerce_customer_contact_readonly.py及新test；本parent仍只拥有router/read_http和本E/D-wave。当前还不改路由，不改Web/DDL/AIP，不部署或原DB写。

reader用一个核实READONLY RR snapshot、transaction_timestamp cutoff、3秒statement/0.5秒lock/10秒跨查询与逐行时间门。frequency policy全部保存修订COUNT和withdrawal全部观察COUNT保留，不冒充活跃策略/去重客户/当前Consent；SQL聚合outer/payload tenant/id/rev/hash/time一致，任何invalid/future/SQL错误稳定拒绝而不补零。两COUNT不传输全部payload，不伪称重算全部未展示行签名。

选中latest Start固定tenant与created_at/revision/decision_id排序LIMIT1；SQLCASE单行1MiB/DTO1MiB/总8MiB，观察LIMIT257拒绝超过256而不截断；start item最多原合同1000，reservation或skip withdrawal互斥最多1000，全部payload最多1280行。精确读取冻结Batch/原prepared前版及四policy，复用已交付lifecycle纯_decode/_validate_batch合同，额外核Start全部eligible item覆盖/exact refs/绑定hash/排序、原typed items+私有reason完整签名/派生ID/ledger/四zero与blockers。频控exact policy与reservation、不可兑换permit、prepared attempt/outbox typed hashes及outer附加列逐项核验；skipped项保存withdrawal sequence及对应历史withdrawal witness核验，不推定当前Consent或进行频控reservation。只读已保存事实，不运行start/receipt/frequency/contact resolver。

原观察按原request JSON签名/派生ID、exact start ref/item、state/resolution/manual case/tenant/time/outer附加列验证，保留unknown和held reservation。先验证原immutable Start与各观察，再通过已验证纯Store适配器复用原service贡献投影：它改变items/ledger但保留原Start contentHash，这是原投影视图，不当作新的已签名Start，也不对投影重新签名。当前真实ActionReceipt resolver仍关闭，保存typed观察不当实际发出或运营授权。

strict raw拒绝missing/extra/coercion、同tenant/time/隐私/超界；hash单独验证后才排除PII误判；新私有reason不能出现在公开DTO、日志或错误。结果完整DTO重验、commands[]、permitRedemption/contactResolution/providerDispatch/send/external五false；错误503而非null/0假成功。正常legacy成功和contact之外其他GET/全部POST原门保留。

## Loop与退出条件

每个前置与reader先方案Prime/合法消费→RED→最小实现→冻结专项及原W6-08/W6-07/相邻customer/price/closure/catalog→原w6_008临时PG快照/RLS/25006/尺寸/隐私→独立代码质量。前置签名修复只交付代码保存合同，不冒充本GET或经营完成。两部分合格后精确提交/fresh维护controller门/单新意图API更新、原真人正式SDK/拒绝边界/650全等/客户原稿适用三宽/现场Prime，准确Delivery与Authority七强及完整remaining接续。

原不可完整验证的历史Start必须明确稳定错误，不回填原reason、不重算旧hash、不重放旧操作。fullC唯一真人最终预算/原部署/自然经营首链/安装全生命周期/八真实场景全部视觉/观察发布全部保留，完整Goal ACTIVE。
